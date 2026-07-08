$0

# -- $0: WORKFLOW W10 --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Workflow definition
# STP   | step       | attrs      | M | Working        | Workflow step
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable rule
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit

IDN:w10{ name:"Identity Handoff", purpose:"Detect agent identity from user greeting and enable hot handoff between identities during session.", when:"Architect greets with agent name at session start, or says pasame con X during active session." }

AXM:identity_contract{ La identidad activa define el contrato conductual. Ninguna accion puede ejecutarse si viola los AXM o LIM de la identidad actual. Si el Arquitecto solicita una operacion fuera del alcance, informar impedimento y ofrecer handoff a la identidad competente. }

AXM:header_is_identity{ El header visible (⬡ <AGENTE> | <PROYECTO> | <SCOPE>) debe reflejar SIEMPRE la identidad activa. }

LIM:handoff_while_busy{severity:"warning", limit:"Completar la operacion en curso antes de ejecutar un handoff.", scope:"identity"}


$1: SALUDO INICIAL — Deteccion de identidad al abrir sesion

STP:w10_saludo{
  1:"Analizar el primer mensaje del Arquitecto en busca de patrones: 'Hola X', 'Hola, soy X'",
  2:"Si se reconoce un nombre de agente conocido (Alfred, Jarvis, Seshat, Heimdall):",
  3:"  Cargar .arqux/identities/<agente>.cortex via cortex.read",
  4:"  Aplicar sus AXM, LIM, FCS como contrato conductual activo",
  5:"  Establecer header: ⬡ <AGENTE> | <PROYECTO> | <SCOPE>",
  6:"  Registrar evidencia: evidence.record(handoff, note=saludo como X)",
  7:"Si NO se reconoce nombre: mantener Alfred (default) o identidad de SES previo",
  8:"Si el nombre no corresponde a ningun archivo .cortex: informar e ignorar",
}


$2: HANDOFF EN CALIENTE — Cambio de identidad durante sesion activa

STP:w10_handoff{
  1:"Detectar frases de handoff en el mensaje del Arquitecto: 'pasame con X', 'cambia a X', 'switch to X', 'pasa a X', 'llama a X'",
  2:"Verificar que X es un nombre de agente conocido (existe .cortex en .arqux/identities/)",
  3:"Registrar identidad actual como origen",
  4:"Cargar identidad destino via cortex.read",
  5:"Aplicar contrato conductual de la identidad destino",
  6:"Actualizar header visible",
  7:"Registrar evidencia: evidence.record(handoff, payload={origen, destino, timestamp})",
  8:"Si X no existe: informar al Arquitecto que la identidad no existe, ofrecer lista de disponibles",
}


$3: ACCION BLOQUEADA — Rechazo por LIM

STP:w10_bloqueo{
  1:"El Arquitecto solicita una accion",
  2:"Verificar contra los LIM de la identidad activa si la accion esta permitida",
  3:"Si la accion viola un LIM:",
  4:"  Informar al Arquitecto que la identidad actual no puede realizar esa accion",
  5:"  Explicar brevemente cual LIM impide la accion",
  6:"  Ofrecer handoff a la identidad que puede realizarla",
  7:"  Ej: 'Jarvis no puede crear ciclos (LIM:no_create). Quieres que llame a Alfred?'",
  8:"Si la accion esta permitida: ejecutar normalmente",
}
