"""User-facing text in every language the CLI is started in.

Only what a person reads lives here. Instructions written for the model -- the system
prompt, the compression prompt, the background-task notices -- stay in English wherever
they are defined: they are not UI, and translating them would change how the model
behaves rather than what the user sees.
"""

CURRENT = {"code": "en"}

STRINGS = {
    "en": {
        "banner.model": "MODEL",
        "banner.tools": "TOOLS",
        "banner.session": "SESSION",
        "banner.cwd": "CWD",
        "banner.tool_count": "{local} local {dot} {ghl} ghl",
        "banner.hint": "/help for commands {dot} shift+tab for auto mode {dot} 'exit' to leave",

        "mode.auto": "auto",
        "mode.approve": "approve",
        "mode.voice": "voice",
        "mode.text": "text",

        "tasks.running": "{count} running",
        "tasks.abandoning": "{count} background task(s) still running — abandoning them",

        "ask.UpdateFile": "apply this change?",
        "ask.MovePath": "move it?",
        "ask.DeleteFile": "delete it?",
        "ask.DeleteDir": "delete it?",
        "ask.SendWhatsappMessage": "send this message?",
        "ask.ClickBrowserElement": "click it?",
        "ask.TypeInBrowser": "type this?",
        "ask.default": "run this?",
        "ask.yes": "yes",
        "ask.no": "no",
        "ask.tell": "tell it what to do",
        "ask.instead": "what should it do instead?",

        "auto.on": "auto mode on — edits apply without asking, shift+tab to stop",
        "auto.off": "auto mode off — edits ask first",

        "voice.on": "voice on — speak, then press enter",
        "voice.off": "voice off",
        "voice.unavailable": "voice unavailable — {error}",
        "voice.failed": "speech failed — {error}",

        "goodbye": "goodbye",
        "error.ghl": "GoHighLevel tools unavailable — {error}",
        "error.web": "web tools unavailable — {error}",

        "cmd.compressing": "compressing...",
        "cmd.nothing_to_compress": "nothing to compress",
        "cmd.compressed": "compressed {before} messages -> summary, {from_} -> {to} tokens (saved {saved})",
        "cmd.cleared": "cleared {count} messages",
        "cmd.model_current": "current: {model}\n  available: {available}",
        "cmd.model_switched": "model -> {model} ({provider})",
        "cmd.unknown": "unknown command {name} — try /help",
        "cmd.help": (
            "/compress  summarise the conversation and drop the transcript\n"
            "  /tokens    show what is filling the context\n"
            "  /clear     drop the conversation entirely\n"
            "  /model     show or switch the model\n"
            "  /voice     toggle talking to it instead of typing\n"
            "  /browser   attach to your own Chrome so it can drive your tabs\n"
            "  /auto      toggle auto mode, for terminals that swallow shift+tab\n"
            "  shift+tab  toggle auto mode — apply edits without asking\n"
            "  exit       leave"
        ),

        "tokens.schemas": "tool schemas",
        "tokens.prefix": "static prefix",
        "tokens.history": "history",
        "tokens.total": "total",
        "tokens.messages": "messages",
        "tokens.floor": "floor {floor} cannot be compressed",

        "workspace.moved": "moved your workspace from {old}/ to {new}/",
        "workspace.both": "both {old}/ and {new}/ exist in your home folder — {old}/ is no longer read, move anything you still want across",
        "workspace.failed": "could not move {old}/ to {new}/ — {error}",
    },
    "es": {
        "banner.model": "MODELO",
        "banner.tools": "HERRAMIENTAS",
        "banner.session": "SESIÓN",
        "banner.cwd": "CARPETA",
        "banner.tool_count": "{local} locales {dot} {ghl} ghl",
        "banner.hint": "/help para comandos {dot} shift+tab para modo auto {dot} 'exit' para salir",

        "mode.auto": "auto",
        "mode.approve": "aprobar",
        "mode.voice": "voz",
        "mode.text": "texto",

        "tasks.running": "{count} en curso",
        "tasks.abandoning": "{count} tarea(s) en segundo plano siguen activas — se abandonan",

        "ask.UpdateFile": "¿aplicar este cambio?",
        "ask.MovePath": "¿moverlo?",
        "ask.DeleteFile": "¿borrarlo?",
        "ask.DeleteDir": "¿borrarlo?",
        "ask.SendWhatsappMessage": "¿enviar este mensaje?",
        "ask.ClickBrowserElement": "¿hacer clic?",
        "ask.TypeInBrowser": "¿escribir esto?",
        "ask.default": "¿ejecutar esto?",
        "ask.yes": "sí",
        "ask.no": "no",
        "ask.tell": "decirle qué hacer",
        "ask.instead": "¿qué debería hacer en su lugar?",

        "auto.on": "modo auto activado — los cambios se aplican sin preguntar, shift+tab para parar",
        "auto.off": "modo auto desactivado — los cambios se preguntan primero",

        "voice.on": "voz activada — habla y pulsa enter",
        "voice.off": "voz desactivada",
        "voice.unavailable": "voz no disponible — {error}",
        "voice.failed": "fallo al hablar — {error}",

        "goodbye": "hasta luego",
        "error.ghl": "herramientas de GoHighLevel no disponibles — {error}",
        "error.web": "herramientas web no disponibles — {error}",

        "cmd.compressing": "comprimiendo...",
        "cmd.nothing_to_compress": "nada que comprimir",
        "cmd.compressed": "comprimidos {before} mensajes -> resumen, {from_} -> {to} tokens (ahorrados {saved})",
        "cmd.cleared": "{count} mensajes borrados",
        "cmd.model_current": "actual: {model}\n  disponibles: {available}",
        "cmd.model_switched": "modelo -> {model} ({provider})",
        "cmd.unknown": "comando desconocido {name} — prueba /help",
        "cmd.help": (
            "/compress  resumir la conversación y descartar el historial\n"
            "  /tokens    ver qué está llenando el contexto\n"
            "  /clear     descartar la conversación entera\n"
            "  /model     ver o cambiar el modelo\n"
            "  /voice     alternar entre hablarle y escribirle\n"
            "  /browser   conectar con tu Chrome para que use tus pestañas\n"
            "  /auto      alternar modo auto, si tu terminal se traga shift+tab\n"
            "  shift+tab  alternar modo auto — aplicar cambios sin preguntar\n"
            "  exit       salir"
        ),

        "tokens.schemas": "esquemas",
        "tokens.prefix": "prefijo fijo",
        "tokens.history": "historial",
        "tokens.total": "total",
        "tokens.messages": "mensajes",
        "tokens.floor": "el mínimo de {floor} no se puede comprimir",

        "workspace.moved": "tu carpeta de trabajo se movió de {old}/ a {new}/",
        "workspace.both": "{old}/ y {new}/ existen en tu carpeta personal — {old}/ ya no se lee, mueve lo que quieras conservar",
        "workspace.failed": "no se pudo mover {old}/ a {new}/ — {error}",
    },
}

# what the model is told, so the assistant answers in the language the user started in.
# English needs no instruction: it is what the system prompt is already written in.
REPLY_LANGUAGE = {
    "es": (
        "Responde siempre en español, en un tono natural y cercano, sin importar el "
        "idioma de las herramientas o de los datos que leas."
    ),
}


def use(code: str) -> None:
    CURRENT["code"] = code if code in STRINGS else "en"


def code() -> str:
    return CURRENT["code"]


def reply_language() -> str:
    return REPLY_LANGUAGE.get(CURRENT["code"], "")


def t(key: str, **values) -> str:
    """The string for the current language. Falls back to English rather than raising:
    a missing translation should read oddly, not take the banner down."""
    text = STRINGS[CURRENT["code"]].get(key) or STRINGS["en"].get(key, key)
    return text.format(**values) if values else text
