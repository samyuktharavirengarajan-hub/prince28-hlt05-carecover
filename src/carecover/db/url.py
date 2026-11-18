from sqlalchemy.engine import make_url


def to_asyncpg_url(raw: str) -> str:
    url = make_url(raw)

    if url.drivername in {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }:
        url = url.set(drivername="postgresql+asyncpg")

    query = dict(url.query)

    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)

    if sslmode and sslmode != "disable":
        query["ssl"] = "require"

    url = url.set(query=query)

    return url.render_as_string(hide_password=False)
