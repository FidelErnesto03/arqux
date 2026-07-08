$0

# -- $0: WORKFLOW W09 —
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# RSK   | risk       | attrs      | M | Prefrontal     | Identified risk

IDN:w09{ name:"CRUD Write Blocked", purpose:"Diagnose and resolve E015_ATOMIC_WRITE_FAILED errors caused by E032/E034 non-bypassable validation on brain.cortex writes." }

RSK:outdated_codec{risk:"CODEC-CORTEX <0.4.3 no tiene auto-repair — force=True no repara E032/E034", mitigation:"Verificar cortex.__version__ >= 0.4.3. Si es menor, actualizar: pip install --upgrade codec-cortex", severity:"high"}


$1: DETECT — Blocked write

STP:w09_detect{
  1:"Handler retorna E015_ATOMIC_WRITE_FAILED con errores non-bypassable",
  2:"Identificar codigos: E032 (missing required fields), E034 (empty required fields)",
  3:"Si hay E032/E034 → pasar a DIAGNOSE",
  4:"Si son otros codigos (E031 secret, E024 missing focus) → escalar a Arquitecto (otros procedimientos)",
  key_rule:"NO intentar bypass manual de validacion. Usar auto-repair o CLI."
}


$2: DIAGNOSE — Which sigils are affected

STP:w09_diagnose{
  1:"Leer brain.cortex y buscar entries sin campos requeridos:",
  "   LNG sin 'prevention' — legacy comun",
  "   OBJ sin 'success' — legacy comun",
  "   SES con output='' — session sin cerrar",
  "   WRK sin 'phase' o 'blocked' — escritura truncada",
  "   RSK sin 'risk','impact','mitigation' — placeholder",
  2:"Verificar version CODEC-CORTEX:",
  "   cortex.__version__ >= 0.4.3 → auto-repair disponible",
  "   cortex.__version__ < 0.4.3 → ACTUALIZAR: pip install --upgrade codec-cortex",
  key_rule:"El auto-repair solo funciona con force=True. force=False sigue bloqueando E032/E034 intencionalmente."
}


$3: RESOLVE — Force write with auto-repair

STP:w09_resolve{
  1:"Llamar al handler con force=True (segundo intento):",
  "   crud_update(path, selector, set_=..., force=True)",
  "   atomic_write_cortex(doc, path, force=True)",
  2:"CODEC-CORTEX v0.4.3+ detecta E032/E034 en diagnostico, repara entries afectadas,",
  "  re-serializa, re-parsea y re-valida automaticamente",
  3:"Si el write succeede: verificar WRK:current limpio",
  "   cortex.read(brain) → WRK sin prefijos '- cycle=' ni acumulaciones",
  4:"Si el write SIGUE fallando: escalar a Arquitecto con el diagnostico completo",
  key_rule:"force=True es seguro — solo completa campos faltantes con defaults. No sobreescribe datos existentes."
}


$4: CLI — Manual brain repair

STP:w09_cli{
  1:"Para reparar un brain sin escribirlo (dry-run):",
  "   arqux brain repair <path> --dry-run",
  2:"Para reparar y escribir:",
  "   arqux brain repair <path> --force",
  3:"El CLI reporta todas las entries reparadas y los campos completados",
  4:"Verificar con: arqux verify <path>",
  note:"CLI brain repair es un complemento opcional. El auto-repair en transactions.py cubre el caso comun."
}


$5: Lesson

LNG:crud_blocked_legacy{type:"contextual", cause:"E032/E034 non-bypassable bloquean writes en brains legacy", lesson:"El auto-repair en CODEC-CORTEX v0.4.3 cura E032/E034 con force=True. Verificar version primero, luego reintentar con force=True. Si falla, escalar."}
