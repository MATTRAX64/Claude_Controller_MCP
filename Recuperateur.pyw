import os, re, traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog

ROOT = Path(__file__).parent.resolve()

BG="#0d0d1a"; CARD="#1a1a35"; ACCENT="#7c5cfc"; GREEN="#2ecc71"; RED="#e74c3c"; TEXT="#e0e0e0"; MUTED="#666"

COMMON_EXTS = ['.cs', '.py', '.pyw', '.js', '.ts', '.json', '.txt', '.lua', '.xml', '.yaml', '.md', '.env']

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Récupérateur de code")
        self.geometry("680x560")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._ext_vars = {}
        self._build()

    def _build(self):
        tk.Label(self, text="📦 RÉCUPÉRATEUR", bg=BG, fg="#fff",
                 font=("Segoe UI", 13, "bold")).pack(pady=(16, 2))
        tk.Label(self, text="Configure l'export puis clique sur Récupérer",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 10))

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=4)

        # ── Colonne gauche : extensions ──────────────────────────
        left = tk.Frame(main, bg=CARD, padx=10, pady=10)
        left.pack(side="left", fill="y", padx=(0, 8))

        tk.Label(left, text="Extensions", bg=CARD, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        for ext in COMMON_EXTS:
            var = tk.BooleanVar(value=ext in {'.cs', '.pyw'})
            self._ext_vars[ext] = var
            tk.Checkbutton(left, text=ext, variable=var,
                           bg=CARD, fg=TEXT, selectcolor="#2a2a50",
                           activebackground=CARD, activeforeground=TEXT,
                           font=("Consolas", 9)).pack(anchor="w")

        tk.Label(left, text="Autres (ex: .cfg,.ini)", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(10, 2))
        self._extra_ext = tk.Entry(left, bg="#0a0a18", fg=TEXT, insertbackground=ACCENT,
                                   relief="flat", font=("Consolas", 9), width=18)
        self._extra_ext.pack(anchor="w", fill="x")

        # ── Colonne droite : config skip + sortie ────────────────
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="Fichiers à ignorer (1 par ligne)", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        sf = tk.Frame(right, bg=CARD, padx=2, pady=2)
        sf.pack(fill="x", pady=(2, 10))
        self._skip_files = tk.Text(sf, bg="#0a0a18", fg=TEXT, font=("Consolas", 8),
                                   height=5, relief="flat", insertbackground=ACCENT)
        self._skip_files.insert("1.0", "Recuperateur.pyw\nPatcheur.pyw\nbot_code.txt\npatch_log.txt")
        self._skip_files.pack(fill="x")

        tk.Label(right, text="Dossiers à ignorer (1 par ligne)", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        sd = tk.Frame(right, bg=CARD, padx=2, pady=2)
        sd.pack(fill="x", pady=(2, 10))
        self._skip_dirs = tk.Text(sd, bg="#0a0a18", fg=TEXT, font=("Consolas", 8),
                                  height=4, relief="flat", insertbackground=ACCENT)
        self._skip_dirs.insert("1.0", "bin\nobj\n.vs\n.git\n__pycache__")
        self._skip_dirs.pack(fill="x")

        tk.Label(right, text="Fichier de sortie", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        of = tk.Frame(right, bg=BG)
        of.pack(fill="x", pady=(2, 8))
        self._out_file = tk.Entry(of, bg="#0a0a18", fg=TEXT, insertbackground=ACCENT,
                                  relief="flat", font=("Consolas", 9))
        self._out_file.insert(0, "bot_code.txt")
        self._out_file.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(of, text="📁", bg="#333", fg=TEXT, relief="flat",
                  cursor="hand2", command=self._browse).pack(side="left")

        # ── Log ──────────────────────────────────────────────────
        lf = tk.Frame(self, bg=CARD, padx=2, pady=2)
        lf.pack(fill="x", padx=16, pady=(4, 0))
        self._log = tk.Text(lf, bg="#0a0a18", fg=MUTED, font=("Consolas", 8),
                            height=3, relief="flat", state="disabled")
        self._log.pack(fill="x")
        for t, c in [("ok", GREEN), ("err", RED), ("info", MUTED)]:
            self._log.tag_configure(t, foreground=c)

        tk.Button(self, text="▶  Récupérer", bg=ACCENT, fg="#fff",
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=18, pady=7, cursor="hand2", command=self._run).pack(pady=12)

    def _browse(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texte", "*.txt"), ("Tous", "*.*")],
            initialfile=self._out_file.get()
        )
        if path:
            self._out_file.delete(0, "end")
            self._out_file.insert(0, path)

    def _log_add(self, msg, tag="info"):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _run(self):
        # Extensions
        exts = {ext for ext, var in self._ext_vars.items() if var.get()}
        for e in self._extra_ext.get().split(","):
            e = e.strip()
            if e:
                if not e.startswith("."): e = "." + e
                exts.add(e.lower())
        if not exts:
            messagebox.showwarning("Attention", "Aucune extension sélectionnée.")
            return

        skip_files = {l.strip() for l in self._skip_files.get("1.0", "end").splitlines() if l.strip()}
        skip_dirs  = {l.strip() for l in self._skip_dirs.get("1.0", "end").splitlines() if l.strip()}

        out_path = Path(self._out_file.get().strip() or "bot_code.txt")
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        skip_files.add(out_path.name)  # toujours ignorer le fichier de sortie lui-même

        lines = []
        count = 0

        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for filename in filenames:
                if filename in skip_files: continue
                ext = os.path.splitext(filename)[1].lower()
                if ext not in exts: continue

                filepath = os.path.join(dirpath, filename)
                relpath  = os.path.relpath(filepath, ROOT)
                lines.append("=" * 60)
                lines.append(f"FICHIER : {relpath}")
                lines.append("=" * 60)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    if ext == ".env":
                        content = re.sub(r'(?m)^([A-Z_]+=)(.+)$', r'\1***', content)
                    lines.append(content)
                    count += 1
                except Exception as e:
                    lines.append(f"[ERREUR : {e}]")
                lines.append("")

        try:
            out_path.write_text("\n".join(lines), encoding="utf-8")
            self._log_add(f"✅ {count} fichier(s) → {out_path.name}", "ok")
        except Exception as e:
            self._log_add(f"❌ Erreur écriture : {e}", "err")

if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        import tkinter as tk2; tk2.Tk().withdraw()
        from tkinter import messagebox as mb
        mb.showerror("Erreur critique", traceback.format_exc())
