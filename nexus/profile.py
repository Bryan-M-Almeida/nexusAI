"""User profile coming from the landing page onboarding form (JSON)."""
import json

from .db import db

# Landing form field -> accepted aliases (English or Portuguese keys).
FIELDS = {
    "name": ("name", "nome"),
    "profession": ("profession", "profissao", "profissão"),
    "routine": ("routine", "rotina"),
    "interests": ("interests", "interesses"),
    "goals": ("goals", "objetivos", "metas"),
    "profile": ("profile", "perfil", "profile_type"),
    "language": ("language", "lang", "idioma"),
}

# Tone and modules per profile, mirroring the landing page "PROFILES" section.
PROFILES = {
    "developer": ("técnico e direto", ["código", "documentação técnica", "agenda", "foco/pomodoro"]),
    "healthcare": ("cuidadoso e preciso", ["primeiros socorros", "plantões", "agenda", "estudos clínicos"]),
    "student": ("didático e encorajador", ["estudos", "provas", "agenda", "resumos"]),
    "designer": ("criativo e visual", ["referências", "projetos", "agenda", "feedbacks"]),
    "entrepreneur": ("objetivo e estratégico", ["finanças", "metas", "reuniões", "indicadores"]),
    "general": ("cordial e claro", ["agenda", "tarefas", "notas", "conhecimento"]),
}
PROFILE_ALIASES = {
    "dev": "developer", "desenvolvedor": "developer", "programador": "developer",
    "saude": "healthcare", "saúde": "healthcare", "health": "healthcare",
    "estudante": "student", "aluno": "student",
    "empreendedor": "entrepreneur", "business": "entrepreneur",
}


def _as_list(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]
    return []


def _guess_profile(profession: str) -> str:
    p = profession.lower()
    for key, words in {
        "developer": ("dev", "program", "software", "engenheir", "full-stack", "backend", "frontend"),
        "healthcare": ("médic", "medic", "enferm", "saúde", "saude", "nurse", "doctor", "fisio"),
        "student": ("estud", "student", "aluno", "universit"),
        "designer": ("design", "ux", "ui", "artist"),
        "entrepreneur": ("empreend", "ceo", "founder", "fundador", "empresár", "business"),
    }.items():
        if any(w in p for w in words):
            return key
    return "general"


def normalize(raw: dict) -> dict:
    """Map an onboarding JSON (any of the accepted key spellings) to the canonical profile."""
    if not isinstance(raw, dict):
        raise ValueError("O perfil deve ser um objeto JSON.")
    raw = raw.get("profile") if isinstance(raw.get("profile"), dict) else raw
    lower = {str(k).lower(): v for k, v in raw.items()}
    out, used = {}, set()
    for field, aliases in FIELDS.items():
        for a in aliases:
            if a in lower and lower[a] not in (None, ""):
                out[field] = lower[a]
                used.add(a)
                break
    if not out.get("name"):
        raise ValueError("O JSON precisa ter ao menos o campo 'name' (ou 'nome').")
    out["interests"] = _as_list(out.get("interests"))
    out["goals"] = _as_list(out.get("goals"))
    out.setdefault("profession", "")
    out.setdefault("routine", "")
    out.setdefault("language", "pt-BR")
    kind = str(out.get("profile") or "").lower()
    kind = PROFILE_ALIASES.get(kind, kind)
    out["profile"] = kind if kind in PROFILES else _guess_profile(str(out["profession"]))
    out["tone"], out["modules"] = PROFILES[out["profile"]]
    # Keep any additional answers from the form so the assistant can use them.
    extras = {k: v for k, v in raw.items() if str(k).lower() not in used}
    if extras:
        out["extra"] = extras
    return out


def import_profile(payload) -> dict:
    data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    profile = normalize(data)
    db.set_profile(profile)
    db.log_action("perfil", f"Perfil importado: {profile['name']} ({profile['profession'] or profile['profile']})")
    return profile


def update_field(field: str, value) -> dict:
    profile = db.get_profile() or {"name": "Usuário"}
    if field in ("interests", "goals"):
        profile[field] = _as_list(value) if not isinstance(value, list) else value
    else:
        profile[field] = value
    db.set_profile(profile)
    db.log_action("perfil", f"Perfil atualizado: {field}")
    return profile


def describe(profile: dict | None) -> str:
    if not profile:
        return "Perfil ainda não configurado. Peça gentilmente que o usuário importe o JSON do formulário da landing page."
    lines = [f"Nome: {profile.get('name')}"]
    if profile.get("profession"):
        lines.append(f"Profissão: {profile['profession']} (perfil {profile.get('profile')})")
    if profile.get("routine"):
        lines.append(f"Rotina: {profile['routine']}")
    if profile.get("interests"):
        lines.append("Interesses: " + ", ".join(profile["interests"]))
    if profile.get("goals"):
        lines.append("Objetivos: " + ", ".join(profile["goals"]))
    lines.append(f"Tom de voz: {profile.get('tone', 'natural')}; módulos: {', '.join(profile.get('modules', []))}")
    for k, v in (profile.get("extra") or {}).items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)
