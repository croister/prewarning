def to_unicode(obj, charset="utf-8", errors="strict"):
    if obj is None:
        return None

    if not isinstance(obj, bytes):
        return str(obj)

    return obj.decode(charset, errors)
