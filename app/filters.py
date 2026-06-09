from markupsafe import Markup, escape


def nl2br(value):
    if value is None:
        return ""
    return Markup("<br>".join(escape(value).splitlines()))
