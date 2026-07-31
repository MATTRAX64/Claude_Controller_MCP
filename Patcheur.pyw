import os, shutil, traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

ROOT = Path(__file__).parent.resolve()
PROTECTED = {"Recuperateur.pyw", "Token.env", "Patcheur.pyw"}

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
    if not str(p).startswith(str(ROOT)): raise PermissionError(f"Hors dossier : {s}")
    if p.name in PROTECTED: raise PermissionError(f"Protégé : {p.name}")
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

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Appliquer Patch"); self.geometry("620x520"); self.resizable(False, False)
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
        tk.Button(bf, text="▶  Appliquer", bg=ACCENT, fg="#fff",
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  padx=18, pady=7, cursor="hand2", command=self._run).pack()

        self._log = tk.Text(self, bg=BG, fg=MUTED, font=("Consolas", 8),
                            height=4, relief="flat", state="disabled")
        self._log.pack(fill="x", padx=16, pady=(0, 10))
        for t, c in [("ok", GREEN), ("err", RED), ("info", MUTED)]:
            self._log.tag_configure(t, foreground=c)

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

try:
    from tkinterdnd2 import TkinterDnD
    class App(TkinterDnD.Tk, App):
        def __init__(self): TkinterDnD.Tk.__init__(self); App._build(self)
except: pass

if __name__ == "__main__":
    try: App().mainloop()
    except Exception:
        import tkinter as tk2; tk2.Tk().withdraw()
        from tkinter import messagebox as mb
        mb.showerror("Erreur critique", traceback.format_exc())
