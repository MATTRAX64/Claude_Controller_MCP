"""IA Prompting : Patcheur et Récupérateur, application autonome."""
import os, re, shutil, traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog

ROOT = Path(__file__).parent.resolve()
PROTECTED = {"recuperateur.pyw", "token.env", "patcheur.pyw", Path(__file__).name.casefold()}

# ══════════════════════════════════════════════════════
#  FORMAT DU PATCH
#  W:chemin          → écriture complète du fichier
#  D:chemin          → suppression d'un fichier
#  MD:chemin         → suppression d'un dossier
#  MC:chemin         → création d'un dossier
#  RL:chemin:L       → remplace la ligne L (1-indexé)
#  RL:chemin:L1:L2   → remplace les lignes L1 à L2 inclus
#  DL:chemin:L       → supprime la ligne L
#  DL:chemin:L1:L2   → supprime les lignes L1 à L2
#  IL:chemin:L       → insère après la ligne L (0 = début)
# ══════════════════════════════════════════════════════

def _safe(s):
    p = (ROOT / s).resolve()
    if not p.is_relative_to(ROOT): raise PermissionError(f"Hors dossier : {s}")
    if p.name.casefold() in PROTECTED: raise PermissionError(f"Protégé : {p.name}")
    if p == ROOT: raise PermissionError("Racine protégée")
    return p

TAGS = ("W:", "D:", "MD:", "MC:", "RL:", "DL:", "IL:")

def _read_block(lines, i):
    """Lit les lignes de contenu jusqu'au prochain tag."""
    cl = []
    while i < len(lines):
        s = lines[i].rstrip()
        if s and any(s.startswith(t) for t in TAGS): break
        cl.append(lines[i]); i += 1
    while cl and not cl[-1].strip(): cl.pop()
    return i, "\n".join(cl)

def _parse_line_args(raw):
    """Parse 'chemin:L' ou 'chemin:L1:L2' → (chemin, start, end)."""
    parts = raw.strip().rsplit(":", 2)
    # Essai : dernier(s) élément(s) sont des entiers
    try:
        if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
            return ":".join(parts[:-2]), int(parts[-2]), int(parts[-1])
        if len(parts) >= 2 and parts[-1].isdigit():
            path = ":".join(parts[:-1])
            n = int(parts[-1])
            return path, n, n
    except ValueError: pass
    raise ValueError(f"Format invalide : {raw}")

def parse(text):
    ops = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        l = lines[i].rstrip()
        if not l or l.startswith("#"): i += 1; continue

        if l.startswith("W:"):
            path = l[2:].strip(); i += 1
            i, content = _read_block(lines, i)
            ops.append(("W", path, None, None, content))

        elif l.startswith("D:"):  ops.append(("D",  l[2:].strip(), None, None, None)); i += 1
        elif l.startswith("MD:"): ops.append(("MD", l[3:].strip(), None, None, None)); i += 1
        elif l.startswith("MC:"): ops.append(("MC", l[3:].strip(), None, None, None)); i += 1

        elif l.startswith("RL:"):
            path, start, end = _parse_line_args(l[3:])
            i += 1; i, content = _read_block(lines, i)
            ops.append(("RL", path, start, end, content))

        elif l.startswith("DL:"):
            path, start, end = _parse_line_args(l[3:])
            ops.append(("DL", path, start, end, None)); i += 1

        elif l.startswith("IL:"):
            path, after, _ = _parse_line_args(l[3:])
            i += 1; i, content = _read_block(lines, i)
            ops.append(("IL", path, after, None, content))

        else: i += 1
    return ops

def apply(ops):
    log = []; err = []
    for a, s, start, end, content in ops:
        try:
            if a == "W":
                p = _safe(s); p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8"); log.append(f"✅ W  {s}")

            elif a == "D":
                p = _safe(s)
                if p.exists(): p.unlink(); log.append(f"🗑 D  {s}")
                else: log.append(f"⚠ D  {s} introuvable")

            elif a == "MD":
                p = _safe(s)
                if p.is_dir(): shutil.rmtree(p); log.append(f"🗑 MD {s}/")
                else: log.append(f"⚠ MD {s}/ introuvable")

            elif a == "MC":
                p = _safe(s); p.mkdir(parents=True, exist_ok=True); log.append(f"📁 MC {s}")

            elif a in ("RL", "DL", "IL"):
                p = _safe(s)
                if not p.exists(): raise FileNotFoundError(f"{s} introuvable")
                file_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()

                if a == "RL":
                    # Remplace lignes start..end (1-indexé, inclus)
                    file_lines[start - 1 : end] = content.splitlines()
                    log.append(f"✏ RL  {s}  L{start}" + (f"-{end}" if end != start else ""))

                elif a == "DL":
                    del file_lines[start - 1 : end]
                    log.append(f"✂ DL  {s}  L{start}" + (f"-{end}" if end != start else ""))

                elif a == "IL":
                    # Insère après la ligne `start` (0 = tout au début)
                    file_lines[start:start] = content.splitlines()
                    log.append(f"➕ IL  {s}  après L{start}")

                p.write_text("\n".join(file_lines), encoding="utf-8")

        except Exception as e:
            err.append(f"❌ {a}  {s}  →  {e}")
    return log, err

# ── UI ────────────────────────────────────────────────────────────────
BG="#0d0d1a"; CARD="#1a1a35"; ACCENT="#7c5cfc"; GREEN="#2ecc71"; RED="#e74c3c"; TEXT="#e0e0e0"; MUTED="#666"

class PatcheurFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.configure(bg=BG); self._build()

    def _build(self):
        tk.Label(self, text="⚡ APPLIQUER PATCH", bg=BG, fg="#fff",
                 font=("Segoe UI", 13, "bold")).pack(pady=(18, 6))
        tk.Label(self, text="Colle le patch.txt",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack()

        # Légende compacte
        legend = "  W: fichier complet   D: suppr fichier   RL: remplacer ligne(s)   DL: suppr ligne(s)   IL: insérer après ligne"
        tk.Label(self, text=legend, bg=BG, fg="#444", font=("Consolas", 7)).pack(pady=(2, 0))

        f = tk.Frame(self, bg=CARD, padx=2, pady=2); f.pack(fill="both", expand=True, padx=16, pady=10)
        self._txt = tk.Text(f, bg="#0a0a18", fg=TEXT, font=("Consolas", 9),
                            insertbackground=ACCENT, relief="flat", wrap="none")
        sb = tk.Scrollbar(f, command=self._txt.yview); sb.pack(side="right", fill="y")
        self._txt.configure(yscrollcommand=sb.set); self._txt.pack(fill="both", expand=True)

        try:
            self._txt.drop_target_register("DND_Files")
            self._txt.dnd_bind("<<Drop>>", self._drop)
        except: pass

        bf = tk.Frame(self, bg=BG); bf.pack(pady=(0, 14))
        tk.Button(bf, text="Ouvrir un patch…", bg=CARD, fg=TEXT, relief="flat",
                  padx=12, pady=7, command=self._open_patch).pack(side="left", padx=6)
        tk.Button(bf, text="▶  Appliquer", bg=ACCENT, fg="#fff",
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=18, pady=7, cursor="hand2", command=self._run).pack(side="left", padx=6)

        self._log = tk.Text(self, bg=BG, fg=MUTED, font=("Consolas", 8),
                            height=4, relief="flat", state="disabled")
        self._log.pack(fill="x", padx=16, pady=(0, 10))
        for t, c in [("ok", GREEN), ("err", RED), ("info", MUTED)]:
            self._log.tag_configure(t, foreground=c)

    def _open_patch(self):
        path = filedialog.askopenfilename(parent=self, title="Ouvrir un patch", filetypes=[("Texte", "*.txt"), ("Tous", "*.*")])
        if path:
            try:
                txt = Path(path).read_text(encoding="utf-8-sig")
                self._txt.delete("1.0", "end"); self._txt.insert("1.0", txt)
            except Exception as ex: self._log_add(str(ex), "err")

    def _drop(self, e):
        path = e.data.strip("{}")
        try:
            txt = Path(path).read_text(encoding="utf-8")
            self._txt.delete("1.0", "end"); self._txt.insert("1.0", txt)
        except Exception as ex: self._log_add(f"❌ {ex}", "err")

    def _log_add(self, msg, tag="info"):
        self._log.configure(state="normal")
        self._log.insert("end", msg + "\n", tag)
        self._log.see("end"); self._log.configure(state="disabled")

    def _run(self):
        txt = self._txt.get("1.0", "end").strip()
        if not txt: messagebox.showinfo("Info", "Colle d'abord un patch."); return

        try:
            ops = parse(txt)
        except Exception as e:
            messagebox.showerror("Erreur de parsing", str(e)); return

        if not ops: messagebox.showinfo("Info", "Aucune opération détectée."); return

        def desc(op):
            a, s, start, end, _ = op
            if a in ("RL", "DL"):
                r = f"L{start}" + (f"-{end}" if end and end != start else "")
                return f"  {a}  {s}  [{r}]"
            if a == "IL":
                return f"  {a}  {s}  [après L{start}]"
            return f"  {a}  {s}"

        summary = "\n".join(desc(op) for op in ops)
        if not messagebox.askyesno("Confirmer", f"{len(ops)} opération(s) :\n\n{summary}\n\nContinuer ?"): return

        log, err = apply(ops)
        for l in log: self._log_add(l, "ok" if l.startswith("✅") else "info")
        for e in err: self._log_add(e, "err")
        (ROOT / "patch_log.txt").write_text("\n".join(log + err), encoding="utf-8")
        if err: messagebox.showwarning("Terminé avec erreurs", "\n".join(err))
        else:   messagebox.showinfo("✅ Succès", f"{len(log)} opération(s) appliquée(s).")


COMMON_EXTS = ['.cs', '.py', '.pyw', '.js', '.ts', '.json', '.txt', '.lua', '.xml', '.yaml', '.md', '.env']

class RecuperateurFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
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
        self._skip_files.insert("1.0", "Recuperateur.pyw\nPatcheur.pyw\n" + Path(__file__).name + "\nbot_code.txt\npatch_log.txt")
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
        skip_files.add(Path(__file__).name)
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


# One root window, two persistent tool panels.
try:
    from tkinterdnd2 import TkinterDnD
    WindowBase = TkinterDnD.Tk
except ImportError:
    WindowBase = tk.Tk

class IAPromptingApp(WindowBase):
    def __init__(self):
        super().__init__()
        self.title("IA Prompting — Patcheur & Récupérateur")
        self.geometry("860x780")
        self.minsize(780, 740)
        self.configure(bg=BG)
        header = tk.Frame(self, bg=CARD, padx=16, pady=12)
        header.pack(fill="x")
        tk.Button(header, text="⌂  Choisir un outil", command=lambda: self.show("home"),
                  bg=ACCENT, fg="white", relief="flat", padx=12, pady=6).pack(side="left")
        self.heading = tk.Label(header, text="", bg=CARD, fg=TEXT, font=("Segoe UI", 12, "bold"))
        self.heading.pack(side="left", padx=18)
        tk.Label(self, text="Dossier de travail : " + str(ROOT), bg=BG, fg=TEXT,
                 anchor="w", wraplength=820, font=("Segoe UI", 9)).pack(fill="x", padx=16, pady=8)
        host = tk.Frame(self, bg=BG)
        host.pack(fill="both", expand=True)
        host.rowconfigure(0, weight=1); host.columnconfigure(0, weight=1)
        home = tk.Frame(host, bg=BG)
        tk.Label(home, text="Que veux-tu faire ?", bg=BG, fg="white",
                 font=("Segoe UI", 23, "bold")).pack(pady=(70, 14))
        tk.Label(home, text="Deux outils réunis dans un seul script.", bg=BG, fg=TEXT,
                 font=("Segoe UI", 11)).pack(pady=(0, 28))
        for key, title, detail in (
            ("recuperateur", "Récupérateur", "Rassembler les fichiers de code dans un fichier texte"),
            ("patcheur", "Patcheur", "Appliquer un patch pour modifier les fichiers"),
        ):
            tk.Button(home, text=title + "\n" + detail,
                      command=lambda k=key: self.show(k), bg=CARD, fg=TEXT,
                      activebackground=ACCENT, activeforeground="white", relief="flat",
                      font=("Segoe UI", 12), padx=24, pady=22, cursor="hand2").pack(fill="x", padx=65, pady=10)
        self.pages = {"home": home, "patcheur": PatcheurFrame(host), "recuperateur": RecuperateurFrame(host)}
        for panel in self.pages.values(): panel.grid(row=0, column=0, sticky="nsew")
        self.show("home")

    def show(self, name):
        self.pages[name].tkraise()
        self.heading.configure(text={"home": "IA Prompting", "patcheur": "Patcheur", "recuperateur": "Récupérateur"}[name])

if __name__ == "__main__":
    try:
        IAPromptingApp().mainloop()
    except Exception:
        messagebox.showerror("Erreur critique", traceback.format_exc())
