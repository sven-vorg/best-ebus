from collections import defaultdict
        
import re
import duckdb
import graphviz

class DBVisualisation:

    def __init__(self, db_path):
        self.db_path = db_path



    def export_mermaid(self, db_path, out_file="schema.mmd"):
        con = duckdb.connect(db_path, read_only=True)

        cols = con.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            ORDER BY table_name, ordinal_position
        """).fetchall()

        schema = defaultdict(list)
        for table, col, dtype in cols:
            schema[table].append((col, dtype))

        fks = self._get_foreign_keys(con)

        lines = ["erDiagram"]

        for table, columns in schema.items():
            safe_table = self._sanitize_mermaid_token(table)
            lines.append(f"    {safe_table} {{")
            for col, dtype in columns:
                clean_type = self._sanitize_mermaid_token(dtype)
                clean_col = self._sanitize_mermaid_token(col)
                lines.append(f"        {clean_type} {clean_col}")
            lines.append("    }")

        for table_name, fk_cols, ref_table, ref_cols in fks:
            safe_src = self._sanitize_mermaid_token(table_name)
            safe_ref = self._sanitize_mermaid_token(ref_table)
            lines.append(f'    {safe_src} }}o--|| {safe_ref} : "FK"')

        with open(out_file, "w") as f:
            f.write("\n".join(lines))

        print(f"Written to {out_file}")
        return "\n".join(lines)

    # Mermaid Helpers

    def _sanitize_mermaid_token(self,s):
        # replace anything that's not alnum/underscore with underscore
        s = re.sub(r"[^\w]", "_", s)
        # mermaid tokens must start with a letter or underscore, not a digit
        if re.match(r"^\d", s):
            s = "_" + s
        return s

    def _has_referenced_cols(self, con):
        try:
            con.execute("SELECT referenced_table FROM duckdb_constraints() LIMIT 1")
            return True
        except Exception:
            return False

    def _get_foreign_keys(self, con):
        rows = con.execute("""
            SELECT table_name, constraint_column_names, constraint_text
            FROM duckdb_constraints()
            WHERE constraint_type = 'FOREIGN KEY'
        """).fetchall()

        fks = []
        pattern = re.compile(r"REFERENCES\s+(\w+)\s*\(([^)]+)\)", re.IGNORECASE)

        for table_name, fk_cols, constraint_text in rows:
            match = pattern.search(constraint_text or "")
            if match:
                ref_table = match.group(1)
                ref_cols = [c.strip() for c in match.group(2).split(",")]
                fks.append((table_name, fk_cols, ref_table, ref_cols))
            else:
                print(f"Could not parse constraint: {constraint_text}")

        return fks

    def create_diagram(self):

        con = duckdb.connect(self.db_path)

        tables = con.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            ORDER BY table_name, ordinal_position
        """).fetchall()

        dot = graphviz.Digraph(node_attr={"shape": "plaintext"})

        # group columns by table
        from collections import defaultdict
        schema = defaultdict(list)
        for table, col, dtype in tables:
            schema[table].append((col, dtype))

        for table, cols in schema.items():
            label = f'<<TABLE BORDER="1" CELLBORDER="0"><TR><TD BGCOLOR="lightblue"><B>{table}</B></TD></TR>'
            for col, dtype in cols:
                label += f'<TR><TD ALIGN="LEFT">{col} : {dtype}</TD></TR>'
            label += "</TABLE>>"
            dot.node(table, label=label)

        # add foreign keys if you have them defined via constraints
        fks = con.execute("""
            SELECT constraint_column_names, referenced_table
            FROM duckdb_constraints()
            WHERE constraint_type = 'FOREIGN KEY'
        """).fetchall()

        dot.render("C:/Users/svens/Documents/FU-Berlin/BeST-eBuS/best-ebus/scenario/eBuS/docs/schema", format="svg", cleanup=True)

if __name__ == "__main__":
    db_path = "best-ebus/scenario/eBuS/database/ebus.db"
    visualizer = DBVisualisation(db_path)
    visualizer.create_diagram()
    visualizer.export_mermaid(db_path, out_file="best-ebus/scenario/eBuS/docs/schema.mmd")