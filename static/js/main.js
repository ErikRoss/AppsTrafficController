function switchAddAliasForm() {
    let aliasType = document.getElementById("alias_category").value;
    let aliasAppsLabel = document.getElementById("alias_apps-label");
    let aliasAppsSelector = document.getElementById("alias_apps");

    if (aliasType === "split") {
        aliasAppsLabel.style.removeProperty("display");
        aliasAppsSelector.style.removeProperty("display");
    }
    else {
        aliasAppsLabel.style.display = "none";
        aliasAppsSelector.style.display = "none";
    }
}
