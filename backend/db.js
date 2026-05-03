require("dotenv").config();
const sqlite3 = require("sqlite3").verbose();
const path = require("path");
const DB_FILE = process.env.DB_FILE ? path.resolve(process.env.DB_FILE) : path.join(__dirname, "database.demo.db");
const db = new sqlite3.Database(DB_FILE, err => { if (err) console.error("DB error:", err); else console.log("SQLite connected:", DB_FILE); });
db.run("PRAGMA journal_mode=WAL"); db.run("PRAGMA foreign_keys=ON");
function get(sql, params=[]) { return new Promise((res,rej) => db.get(sql,params,(err,row) => err?rej(err):res(row))); }
function all(sql, params=[]) { return new Promise((res,rej) => db.all(sql,params,(err,rows) => err?rej(err):res(rows))); }
function run(sql, params=[]) { return new Promise((res,rej) => db.run(sql,params,function(err){ err?rej(err):res({lastID:this.lastID,changes:this.changes}); })); }
module.exports = { db, get, all, run };
