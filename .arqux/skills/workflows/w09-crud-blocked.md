$0

# -- $0: WORKFLOW W09 --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# LNG   | lesson     | attrs      | M | Episodic       | Learned lesson
# RSK   | risk       | attrs      | M | Prefrontal     | Identified risk

IDN:w09{ name:"CRUD Write Blocked", purpose:"Diagnose and resolve E032/E034 non-bypassable validation errors on brain.cortex writes." }

RSK:outdated_codec{risk:"CODEC-CORTEX <0.4.3 no tiene auto-repair. force=True no repara E032/E034.", mitigation:"Verificar cortex.__version__ >= 0.4.3. Actualizar: pip install --upgrade codec-cortex.", severity:"high"}


$1: DETECT — Blocked write

STP:w09_detect{ 1:"Handler retorna E015_ATOMIC_WRITE_FAILED con errores non-bypassable.", 2:"Identificar codigos: E032 (missing required fields), E034 (empty required fields).", 3:"Si hay E032/E034 → DIAGNOSE.", 4:"Otros codigos (E031 secret, E024 missing focus) → escalar a Arquitecto.", key_rule:"NO intentar bypass manual. Usar auto-repair o CLI." }


$2: DIAGNOSE — Which sigils are affected

STP:w09_diagnose{ 1:"Leer brain.cortex, buscar entries sin campos requeridos: LNG sin prevention, OBJ sin success, SES con output vacio, RSK placeholders.", 2:"Verificar version CODEC-CORTEX: cortex.__version__ >= 0.4.3 → auto-repair disponible.", key_rule:"Auto-repair solo con force=True. force=False sigue bloqueando E032/E034." }


$3: RESOLVE — Force write con auto-repair

STP:w09_resolve{ 1:"Llamar handler con force=True: crud_update(path, selector, set_=..., force=True)", 2:"CODEC-CORTEX v0.4.3+ repara E032/E034 automaticamente: completa fields faltantes con defaults.", 3:"Si succeede: verificar WRK:current limpio sin acumulaciones.", 4:"Si sigue fallando: escalar a Arquitecto.", key_rule:"force=True es seguro. Solo completa campos faltantes, no sobreescribe datos existentes." }


$4: CLI — Manual brain repair

STP:w09_cli{ 1:"`arqux brain repair <path> --dry-run` para previsualizar reparacion.", 2:"`arqux brain repair <path> --force` para reparar y escribir.", 3:"CLI reporta entries reparadas y campos completados.", 4:"Verificar con `arqux verify <path>`.", note:"CLI brain repair es opcional. Auto-repair en transactions.py cubre el caso comun." }


$5: Lesson

LNG:crud_blocked_legacy{type:"contextual", cause:"E032/E034 bloquean writes en brains legacy", lesson:"Auto-repair CODEC-CORTEX v0.4.3 cura E032/E034 con force=True. Verificar version, reintentar con force=True. Si falla, escalar."}