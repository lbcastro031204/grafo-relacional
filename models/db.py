from neo4j import GraphDatabase
from config.settings import settings


class DB:
    """
    Wrapper singleton para a conexão Neo4j.
    Usado por todos os modelos e agentes.
    """
    _driver = None

    @classmethod
    def driver(cls):
        if cls._driver is None:
            cls._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return cls._driver

    @classmethod
    def run(cls, query: str, **params):
        with cls.driver().session() as session:
            result = session.run(query, **params)
            return [record.data() for record in result]

    @classmethod
    def close(cls):
        if cls._driver:
            cls._driver.close()
            cls._driver = None