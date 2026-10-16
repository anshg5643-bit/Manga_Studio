(() => {
  const { $ } = FK;
  const fill = () => { const u = FK.user; if (!u) return; $("#name").value = u.name; $("#email").value = u.email; $("#mk").checked = u.marketing; $("#curRow").hidden = !u.hasPassword; $("#pwTitle").textContent = u.hasPassword ? "Change password" : "Set a password"; };
  document.addEventListener("fk:ready", fill); document.addEventListener("fk:auth", fill);
  $("#saveP").onclick = async () => { try { FK.user = (await FK.patch("/api/account", { name: $("#name").value, marketing: $("#mk").checked })).user; FK.renderAcct(); $("#pMsg").textContent = "Saved."; } catch (e) { $("#pMsg").textContent = e.message; } };
  $("#savePw").onclick = async () => { const e = $("#pwErr"); e.hidden = true; try { await FK.post("/api/account/password", { current: $("#cur").value, new: $("#new").value }); $("#pwMsg").textContent = "Password updated."; $("#cur").value = $("#new").value = ""; FK.user.hasPassword = true; fill(); } catch (x) { e.textContent = x.message; e.hidden = false; } };
  $("#delAcc").onclick = async () => { if (!confirm("Delete your account and all saved analyses? This cannot be undone.")) return; if (prompt('Type DELETE to confirm') !== "DELETE") return; await FK.del("/api/account"); location.href = "/"; };
})();
