frappe.ui.form.on("Reckon HR Policy Settings", {
    refresh(frm) {
        frm.add_custom_button(__("Refresh Setup Status"), () => frm.call("refresh_setup").then(() => frm.reload_doc()));
    }
});
