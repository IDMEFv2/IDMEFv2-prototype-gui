from prewikka import version
from prewikka.database import SQLScript


class SQLUpdate(SQLScript):
    type = "install"
    branch = version.__branch__
    version = "0"

    def run(self):
        self.query("""
DROP TABLE IF EXISTS Prewikka_inputplugin;

CREATE TABLE Prewikka_inputplugin (
        id BIGINT UNSIGNED NOT NULL PRIMARY KEY AUTO_INCREMENT,
        list_name TEXT NOT NULL,
        list_content TEXT NOT NULL
) ENGINE=InnoDB;
""")
