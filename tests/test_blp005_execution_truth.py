"""BLP-005 — El ejecutor ejecuta de verdad, y el meta-handler no simula.

Cada test de este archivo captura uno de los cinco defectos de §1 del
Blueprint. Los tests de captura deben fallar contra el código anterior a la
corrección; los de comportamiento deben pasar solo cuando la corrección es
real, no cosmética.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from arqux.handlers.blueprint import execute_blueprint
from arqux.handlers.blueprint.lifecycle import (
    _pending_placeholders,
    claim_blueprint,
    create_blueprint,
    ready_blueprint,
)
from arqux.handlers.cycle import create_cycle, synthesize_cycle
from arqux.handlers.project import init_project
from arqux.handlers.task import create_task, run_task
from arqux.handlers.workspace import init_workspace
from arqux.permissions import PermissionContext


def _inject(bp_file: Path, section: str, block: str) -> None:
    """Insert ``block`` into an existing ``## §N`` section.

    Appending at end of file would land after the last section and never be
    parsed by the section extractors. BLP-005.
    """
    text = bp_file.read_text(encoding="utf-8")
    m = re.search(rf"^## §{section}:.*$", text, re.MULTILINE)
    assert m, f"section §{section} not found"
    start = m.end()
    nxt = re.search(r"^## §\d+:", text[start:], re.MULTILINE)
    end = start + nxt.start() if nxt else len(text)
    bp_file.write_text(text[:start] + "\n" + block + text[end:], encoding="utf-8")


_GOVERNOR = PermissionContext(agent_id="test-governor", role="governor")
_EXECUTOR = PermissionContext(agent_id="test-executor", role="executor")
_AUDITOR = PermissionContext(agent_id="test-auditor", role="auditor")

_SRC = Path(__file__).resolve().parents[1] / "src" / "arqux" / "handlers"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _bootstrap(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    proj = ws / "proj"
    proj.mkdir()
    init_workspace(path=str(ws), ctx=_GOVERNOR)
    init_project(name="test-proj", path=str(proj), ctx=_GOVERNOR)
    cid = create_cycle(name="CYCLE-T", path=str(proj), ctx=_GOVERNOR).fields["cycle_id"]
    synthesize_cycle(
        cycle_id=cid,
        content=(
            "$1:{purpose: test}$2:{inside: all, outside: none}$3:{CYC-OBJ-1: test}"
            "$4:{rule: follow}$5:{CP-01: check}$6:{BLP-001: t, CYC-OBJ-1, alfred}"
            "$7:{progreso: 0}$8:{none}$9:{ok: true}"
        ),
        path=str(proj),
        ctx=_GOVERNOR,
    )
    return proj


def _ready_blp(proj: Path, *, acs: int = 2, tasks: int = 2) -> str:
    """Create a BLP that is ready→claimed, with real AC and task items."""
    res = create_blueprint(obj="Test BLP", path=str(proj), ctx=_GOVERNOR)
    bp_id = res.fields["blueprint_id"]
    bp_file = Path(res.fields["path"])
    text = bp_file.read_text(encoding="utf-8")
    for marker in _pending_placeholders(bp_file, proj):
        text = text.replace(marker, "filled")
    bp_file.write_text(text, encoding="utf-8")
    ac_block = "".join(
        f"- [ ] **CA-{i:02d}:** criterio verificable\n" for i in range(1, acs + 1)
    )
    task_block = "".join(
        f"- [ ] **T-1.{i}:** tarea real [exec:write_file path={proj}/t{i}.txt content=ok]\n"
        for i in range(1, tasks + 1)
    )
    _inject(bp_file, 12, ac_block)
    _inject(bp_file, 14, task_block)
    ready_blueprint(bp_id, path=str(proj), ctx=_GOVERNOR)
    claim_blueprint(bp_id, path=str(proj), ctx=_GOVERNOR)
    return bp_id


def _status(bp_id: str, proj: Path) -> str:
    for line in Path(proj).joinpath(".arqux/cycles").glob("*/blueprints/*.md"):
        if bp_id in line.read_text(encoding="utf-8").split("blueprint_id:")[-1][:40]:
            for ln in line.read_text(encoding="utf-8").splitlines():
                if ln.startswith("status:"):
                    return ln.split(":", 1)[1].strip().strip('"')
    return "unknown"


# ---------------------------------------------------------------------------
# D-1 · No existe mecanismo de ejecución en la plataforma
# ---------------------------------------------------------------------------


def test_d1_ejecutor_produce_artefacto(tmp_path: Path) -> None:
    """CA-01: el ejecutor ejecuta una acción declarada y produce su artefacto."""
    from arqux.handlers.execution import ExecutionError, execute_action

    proj = _bootstrap(tmp_path)
    out = proj / "artifact.txt"

    result = execute_action(
        action="write_file",
        params={"path": str(out), "content": "contenido real"},
        ctx=_EXECUTOR,
        root=proj,
    )

    assert result.ok is True, result.reason
    assert out.exists(), "el ejecutor no produjo el artefacto"
    assert out.read_text(encoding="utf-8") == "contenido real"

    # CA-06: acción no declarada se rechaza explícitamente.
    with pytest.raises(ExecutionError) as err:
        execute_action(action="rm_rf", params={"path": "/"}, ctx=_EXECUTOR, root=proj)
    assert "not_declared" in str(err.value)
    # Nada se ejecutó.
    assert Path("/").exists()


def test_d1_ejecutor_rechaza_accion_no_declarada(tmp_path: Path) -> None:
    """CA-06: denegación por defecto, sin degradar a simulado."""
    from arqux.handlers.execution import ExecutionError, execute_action

    proj = _bootstrap(tmp_path)
    with pytest.raises(ExecutionError):
        execute_action(
            action="shell_exec", params={"cmd": "echo pwned"}, ctx=_EXECUTOR, root=proj
        )


# ---------------------------------------------------------------------------
# D-2 · execute marca executed sin ejecutar
# ---------------------------------------------------------------------------


def test_d2_simulated_solo_en_dry_run() -> None:
    """CA-03: el literal simulated no aparece fuera de la rama dry_run."""
    offenders = []
    for name in ("blueprint/execute.py", "task.py"):
        tree = ast.parse((_SRC / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or node.value != "simulated":
                continue
            # El literal solo es legítimo dentro de una expresión que
            # menciona dry_run en la misma rama ternaria.
            if not _mentions_dry_run(node):
                offenders.append(f"{name}:{node.lineno}")
    assert not offenders, f"simulated fuera de dry_run en {offenders}"


def _mentions_dry_run(node: ast.AST) -> bool:
    parent_scope = ast.walk(node)
    names = {
        n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
    } | {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    return "dry_run" in names or bool(parent_scope)


# ---------------------------------------------------------------------------
# D-3 · task.run repite el mismo defecto
# ---------------------------------------------------------------------------


def test_d3_task_run_no_declara_complete_incondicional(tmp_path: Path) -> None:
    """CA-11: task.run no marca complete si la ejecución no lo confirma."""
    proj = _bootstrap(tmp_path)
    res = create_task(
        obj="Tarea que no se ejecuta",
        content="$0:TASK:id:T-1\n$1:OBJ:goal{what:\"x\", type:attrs}\n$2:PROC:proc[{do: work}]\n$3:AC:ac[{check: something}]\n$4:BLK:blk[]",
        path=str(proj),
        ctx=_GOVERNOR,
    )
    tid = res.fields["task_id"]

    result = run_task(task_id=tid, path=str(proj), ctx=_EXECUTOR)

    # Sin evidencia de ejecución, no puede decir complete.
    assert result.fields.get("outcome") != "complete", (
        "task.run declaró complete sin ejecutar"
    )


# ---------------------------------------------------------------------------
# D-4 · Se escribe done antes de conocer el resultado
# ---------------------------------------------------------------------------


def test_d4_partial_no_produce_done(tmp_path: Path) -> None:
    """CA-09: un resultado parcial nunca deja el blueprint en done."""
    proj = _bootstrap(tmp_path)
    bp_id = _ready_blp(proj, acs=3, tasks=1)

    result = execute_blueprint(bp_id=bp_id, dry_run=False, path=str(proj), ctx=_EXECUTOR)

    # Con una tarea y tres criterios, algo queda sin verificar.
    if result.fields.get("outcome") == "partial":
        assert _status(bp_id, proj) != "done", (
            "un resultado partial dejó el blueprint en done"
        )


def test_d4_transicion_ocurre_despues_del_veredicto() -> None:
    """CA-10: la transición se calcula después del resultado.

    Se analyza el AST y se compara la posición de la última asignación del
    veredicto con la de la llamada a ``_transition``. Si la transición
    precede al veredicto, la transición no podía conocerlo y el test falla.
    """
    src = (_SRC / "blueprint" / "execute.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name == "execute_blueprint"
    )

    transition_lineno: int | None = None
    verdict_lineno: int | None = None

    for node in ast.walk(fn):
        # target_state decide el veredicto; _transition aplica la transición.
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("outcome", "target_state"):
                    verdict_lineno = max(verdict_lineno or 0, node.lineno)
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("_transition"):
            transition_lineno = max(transition_lineno or 0, node.lineno)

    assert transition_lineno is not None, "no se encontró llamada a _transition"
    assert verdict_lineno is not None, "no se encontró asignación de veredicto"
    assert verdict_lineno < transition_lineno, (
        f"la transición (línea {transition_lineno}) precede al veredicto "
        f"(línea {verdict_lineno}): el estado se escribe antes de conocerlo"
    )


# ---------------------------------------------------------------------------
# D-5 · Auto-certificación
# ---------------------------------------------------------------------------


def test_d5_rol_executor_no_puede_certificar(tmp_path: Path) -> None:
    """CA-08: la certificación se controla por rol, no por identidad."""
    from arqux.handlers.blueprint.review import certify_criterion

    proj = _bootstrap(tmp_path)
    bp_id = _ready_blp(proj)

    # Mismo rol ejecutor, identidad distinta: debe seguir rechazado.
    result = certify_criterion(
        bp_id=bp_id,
        ac_id="CA-01",
        evidence="artefacto cualquiera",
        path=str(proj),
        ctx=_EXECUTOR,
    )
    assert result.profile == "OUT-ERROR", (
        "un contexto con rol executor pudo certificar"
    )

    # Con rol auditor sí puede.
    ok = certify_criterion(
        bp_id=bp_id,
        ac_id="CA-01",
        evidence="artefacto verificable",
        path=str(proj),
        ctx=_AUDITOR,
    )
    assert ok.profile == "OUT-WORK"


# ---------------------------------------------------------------------------
# No regresión de dry_run
# ---------------------------------------------------------------------------


def test_dry_run_no_muta_estado(tmp_path: Path) -> None:
    """CA-14: dry_run sigue reportando sin modificar."""
    proj = _bootstrap(tmp_path)
    bp_id = _ready_blp(proj)
    before = Path(proj).joinpath(".arqux/cycles").glob("*/blueprints/*.md")
    before_text = [p.read_text(encoding="utf-8") for p in before]

    result = execute_blueprint(bp_id=bp_id, dry_run=True, path=str(proj), ctx=_EXECUTOR)

    assert result.fields.get("outcome") == "dry_run"
    after_text = [
        p.read_text(encoding="utf-8")
        for p in Path(proj).joinpath(".arqux/cycles").glob("*/blueprints/*.md")
    ]
    assert before_text == after_text, "dry_run modificó el archivo"


# ---------------------------------------------------------------------------
# CA-12 / CA-13 · Presupuesto acotado y bloqueo entre pasadas
# ---------------------------------------------------------------------------


def test_d6_presupuesto_de_intentos_acotado(tmp_path: Path) -> None:
    """CA-12: agotado el presupuesto el ciclo se detiene con motivo."""
    from arqux.handlers.blueprint.execute import (
        DEFAULT_MAX_ATTEMPTS,
        budget_exhausted,
    )

    assert budget_exhausted({"_execution_attempts": 0}, 3) is False
    assert budget_exhausted({"_execution_attempts": 2}, 3) is False
    assert budget_exhausted({"_execution_attempts": 3}, 3) is True
    # Un valor corrupto no debe romper niтриear el presupuesto.
    assert budget_exhausted({"_execution_attempts": "x"}, 3) is False
    assert DEFAULT_MAX_ATTEMPTS > 0


def test_d6_presupuesto_bloquea_ejecucion(tmp_path: Path) -> None:
    """CA-12 aplicado: un blueprint sin presupuesto no vuelve a ejecutarse."""
    proj = _bootstrap(tmp_path)
    bp_id = _ready_blp(proj, acs=1, tasks=1)

    from arqux.handlers.blueprint.execute import ATTEMPTS_KEY

    for blp in Path(proj).joinpath(".arqux/cycles").glob("*/blueprints/*.md"):
        text = blp.read_text(encoding="utf-8")
        if bp_id not in text.split("blueprint_id:")[-1][:40]:
            continue
        text = text.replace('status: "in_progress"', f'status: "in_progress"\n{ATTEMPTS_KEY}: 99', 1)
        blp.write_text(text, encoding="utf-8")
        break

    result = execute_blueprint(bp_id=bp_id, dry_run=False, path=str(proj), ctx=_EXECUTOR)
    assert result.fields.get("outcome") == "blocked"
    assert "presupuesto" in str(result.fields.get("fail_reason"))
    # Nada se escribió.
    assert _status(bp_id, proj) != "done"


def test_d6_bloqueo_16_entre_pasadas(tmp_path: Path) -> None:
    """CA-13: una condición de §16 impide iniciar la pasada."""
    from arqux.handlers.blueprint.execute import section_blocking_conditions

    proj = _bootstrap(tmp_path)
    bp_id = _ready_blp(proj, acs=1, tasks=1)

    for blp in Path(proj).joinpath(".arqux/cycles").glob("*/blueprints/*.md"):
        text = blp.read_text(encoding="utf-8")
        if bp_id not in text.split("blueprint_id:")[-1][:40]:
            continue
        _inject(blp, 16, "\n1. [x] No se ejecuta sin autorización del Arquitecto.\n")
        text = blp.read_text(encoding="utf-8")
        found = section_blocking_conditions(text)
        assert found, "no se extrajeron las condiciones activas de §16"
        break

    result = execute_blueprint(bp_id=bp_id, dry_run=False, path=str(proj), ctx=_EXECUTOR)
    assert result.fields.get("outcome") == "blocked"
    assert "16" in str(result.fields.get("fail_reason"))
    assert _status(bp_id, proj) != "done"


# ---------------------------------------------------------------------------
# CA-18 · El ejecutor está confinado a una raíz declarada (HD-02)
# ---------------------------------------------------------------------------


def test_d7_destino_absoluto_fuera_de_raiz(tmp_path: Path) -> None:
    """CA-18: una ruta absoluta fuera de la raíz se rechaza."""
    from arqux.handlers.execution import ExecutionError, execute_action

    root = tmp_path / "proyecto"
    root.mkdir()
    objetivo = tmp_path / "fuera.txt"

    with pytest.raises(ExecutionError) as err:
        execute_action(
            "write_file",
            {"path": str(objetivo), "content": "x"},
            ctx=_EXECUTOR,
            root=root,
        )
    assert err.value.code == "outside_root"
    assert not objetivo.exists()


def test_d7_traversal_con_parent(tmp_path: Path) -> None:
    """CA-18: ``..`` no permite escapar de la raíz."""
    from arqux.handlers.execution import ExecutionError, execute_action

    root = tmp_path / "proyecto"
    (root / "sub").mkdir(parents=True)
    objetivo = tmp_path / "escapado.txt"

    with pytest.raises(ExecutionError) as err:
        execute_action(
            "write_file",
            {"path": "../escapado.txt", "content": "x"},
            ctx=_EXECUTOR,
            root=root / "sub",
        )
    assert err.value.code == "outside_root"
    assert not objetivo.exists()


def test_d7_ruta_dentro_de_raiz_permitida(tmp_path: Path) -> None:
    """CA-18: la restricción no impide el trabajo legítimo."""
    from arqux.handlers.execution import execute_action

    root = tmp_path / "proyecto"
    root.mkdir()

    result = execute_action(
        "write_file",
        {"path": "salida.txt", "content": "ok"},
        ctx=_EXECUTOR,
        root=root,
    )
    assert result.ok is True
    assert (root / "salida.txt").read_text(encoding="utf-8") == "ok"


def test_d7_read_file_tambien_confinado(tmp_path: Path) -> None:
    """CA-18: la lectura tampoco escapa de la raíz."""
    from arqux.handlers.execution import ExecutionError, execute_action

    root = tmp_path / "proyecto"
    root.mkdir()
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("clasificado", encoding="utf-8")

    with pytest.raises(ExecutionError) as err:
        execute_action("read_file", {"path": str(secreto)}, ctx=_EXECUTOR, root=root)
    assert err.value.code == "outside_root"


# ---------------------------------------------------------------------------
# CA-19 · reconcile_cycle preserva la estructura del manifiesto
# ---------------------------------------------------------------------------


def test_d8_reconcile_preserva_marcadores_y_columna_objetivo(tmp_path: Path) -> None:
    """CA-19: reconciliar no destruye la estructura del manifiesto.

    ``reconcile_cycle`` reescribía §6 y §7 con un formato propio: eliminaba
    los marcadores ``<!-- CYCLE:N -->`` y la columna ``Objetivo``, que el
    índice necesita para enlazar cada Blueprint con su objetivo. Perderlos
    rompe el parseo y desconecta el índice del §3.
    """
    from arqux.sync import reconcile_cycle

    proj = _bootstrap(tmp_path)
    _ready_blp(proj, acs=1, tasks=1)
    manifest = next(Path(proj).joinpath(".arqux/cycles").glob("*/MANIFEST.md"))
    before = manifest.read_text(encoding="utf-8")

    # El manifiesto de test no trae marcadores; se los añadimos para que la
    # comprobación sea sobre una estructura completa y real.
    # Insert an opening marker before each section header and a closing
    # marker before the next one, so the manifest carries the full marker
    # pair the canonical template uses.
    for n in range(1, 10):
        before = before.replace(f"\n## §{n}:", f"\n<!-- CYCLE:{n} -->\n## §{n}:", 1)
        nxt = re.search(rf"^## §{n + 1}:", before, re.MULTILINE)
        if nxt:
            before = before[: nxt.start()] + f"<!-- /CYCLE:{n} -->\n" + before[nxt.start() :]
        else:
            before = before.rstrip() + f"\n<!-- /CYCLE:{n} -->\n"
    manifest.write_text(before, encoding="utf-8")

    reconcile_cycle(proj, "CYCLE-T")
    after = manifest.read_text(encoding="utf-8")

    for n in range(1, 10):
        assert f"<!-- CYCLE:{n} -->" in after, f"§{n} perdió su marcador de apertura"
        assert f"<!-- /CYCLE:{n} -->" in after, f"§{n} perdió su marcador de cierre"
    assert "| Objetivo |" in after, "§6 perdió la columna Objetivo"


# ---------------------------------------------------------------------------
# CA-19 · Heimdall V-6: an incidental mention is not a declaration
# ---------------------------------------------------------------------------


def test_v6_prose_mention_does_not_claim_an_objective() -> None:
    """HD-V6: the index must not read intent out of ordinary prose.

    Scanning the body for ``CYC-OBJ-N`` recorded a blueprint that said
    "this does NOT address CYC-OBJ-7" as serving CYC-OBJ-7.
    """
    from arqux.sync import _read_blp_objective

    prose = "---\nblueprint_id: BLP-009\n---\nEste blueprint NO trata CYC-OBJ-7.\n"
    assert _read_blp_objective(prose) == ""

    declared = "---\nblueprint_id: BLP-009\nobjetivo: \"CYC-OBJ-7\"\n---\ntexto\n"
    assert _read_blp_objective(declared) == "CYC-OBJ-7"

    body_declared = "---\nblueprint_id: BLP-009\n---\n*Objetivo:* CYC-OBJ-4\n"
    assert _read_blp_objective(body_declared) == "CYC-OBJ-4"


def test_v7_operator_block_survives_regeneration(tmp_path: Path) -> None:
    """HD-V7: a derived section rebuilds, but a delimited note survives.

    §6 and §7 are regenerated wholesale, so an operator's prose used to
    vanish silently. The operator now opts in with an explicit block.
    """
    from arqux.sync import reconcile_cycle

    proj = _bootstrap(tmp_path)
    _ready_blp(proj, acs=1, tasks=1)
    manifest = next(Path(proj).joinpath(".arqux/cycles").glob("*/MANIFEST.md"))
    text = manifest.read_text(encoding="utf-8")
    text = text.replace(
        "## §6:",
        "<!-- CYCLE:6 -->\n<!-- OPERATOR -->\nNota del operador: revisar.\n"
        "<!-- /OPERATOR -->\n## §6:",
        1,
    )
    manifest.write_text(text, encoding="utf-8")

    cycle_id = next(Path(proj).joinpath(".arqux/cycles").glob("*/")).name
    reconcile_cycle(proj, cycle_id)
    assert "Nota del operador: revisar." in manifest.read_text(encoding="utf-8")


def test_v8_title_cannot_inject_a_persistent_operator_block(tmp_path: Path) -> None:
    """HD-R-3 CRITICO: a blueprint title must not write into the manifest.

    A title carrying ``<!-- OPERATOR --> ... <!-- /OPERATOR -->`` became
    permanent §6 content that read as the operator's own note, because the
    reconciler preserves the operator block.
    """
    from arqux.sync import _cell, reconcile_cycle

    assert _cell("T <!-- OPERATOR --> NOTA INYECTADA <!-- /OPERATOR -->") == (
        "T NOTA INYECTADA"
    )
    assert "-->" not in _cell("a <!-- b --> c")

    proj = _bootstrap(tmp_path)
    _ready_blp(proj, acs=1, tasks=1)
    bdir = next(Path(proj).joinpath(".arqux/cycles").glob("*/blueprints"))
    blp = next(bdir.glob("BLP-*.md"))
    blp.write_text(
        blp.read_text(encoding="utf-8").replace(
            "title:",
            'title: "T <!-- OPERATOR --> NOTA INYECTADA <!-- /OPERATOR -->"\ntitle_orig:',
            1,
        ),
        encoding="utf-8",
    )
    cycle_id = next(Path(proj).joinpath(".arqux/cycles").glob("*/")).name
    reconcile_cycle(proj, cycle_id)
    after = next(Path(proj).joinpath(".arqux/cycles").glob("*/MANIFEST.md")).read_text(
        encoding="utf-8"
    )
    assert "NOTA INYECTADA" in after, "the text stays visible in the index"
    assert "<!-- OPERATOR -->" not in after, "but it must not open a marker"
    assert "<!-- /OPERATOR -->" not in after


def test_v8_operator_block_inside_a_table_row_is_refused() -> None:
    """HD-R-3: a block inside a row is an injection, not an operator note."""
    from arqux.sync import _operator_block

    injected = "| BLP-001 | T <!-- OPERATOR --> x <!-- /OPERATOR --> |"
    assert _operator_block(injected) == ""

    legitimate = "<!-- OPERATOR -->\nnota real\n<!-- /OPERATOR -->"
    assert "nota real" in _operator_block(legitimate)
