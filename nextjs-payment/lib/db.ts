import sqlite3 from "sqlite3";
import path from "path";

const dbPath = path.join(process.cwd(), "data.db");
const db = new sqlite3.Database(dbPath);

db.serialize(() => {
  db.run(`
    CREATE TABLE IF NOT EXISTS orders (
      id TEXT PRIMARY KEY,
      status TEXT
    )
  `);
});

export default db;
