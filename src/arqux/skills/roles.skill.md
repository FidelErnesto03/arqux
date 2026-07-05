$0

# -- $0: ROLES SKILL GLOSSARY --
# Sigil | Name | Type | Risk | Cognitive Layer | Description
# IDN   | identity   | attrs      | B | Semantic       | Role definition
# LIM   | limit      | attrs      | M | Prefrontal     | Hard limit
# AXM   | axiom      | cuerpo     | H | Prefrontal     | Non-negotiable principle


$1: GOVERNOR

IDN:governor{ allowed:"workspace.*, project.*, cycle.*, task.create, task.complete, task.fail, evidence.*, protocol.*, cortex.*", forbidden:"task.claim", purpose:"One per workspace. Decides, assigns, approves, closes." }

AXM:governor{ The governor owns the workspace and its projects. Opens cycles, assigns tasks, records meta-brain lessons. Does NOT implement tasks — that is the executor's job. }


$2: EXECUTOR

IDN:executor{ allowed:"task.claim, task.update, task.complete, task.fail, task.read, task.list, evidence.record, evidence.list, evidence.read, protocol.release", forbidden:"workspace.init, project.init, project.bind, project.unbind, cycle.create, cycle.close, task.create, protocol.adopt", purpose:"Picks up tasks, executes, leaves evidence." }


$3: AUDITOR

IDN:auditor{ allowed:"*.read, *.list, *.status, *.lessons, cortex.read, cortex.verify, cortex.render", forbidden:"all mutations", purpose:"Read-only. Compliance, review, retrospectives." }
