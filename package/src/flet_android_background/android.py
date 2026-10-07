from pathlib import Path
import xml.etree.ElementTree as ET

ANDROID = "http://schemas.android.com/apk/res/android"
NAME = f"{{{ANDROID}}}name"
SERVICE = "dev.alexstoica.background.TaskService"
TYPES = {"dataSync": "DATA_SYNC", "shortService": None, "specialUse": "SPECIAL_USE"}


def configure_android_project(project: str | Path, *, service_type: str,
                              subtype: str = "") -> None:
    """Declare the app's foreground purpose before building its generated Flutter project."""
    if service_type not in TYPES:
        raise ValueError(f"service_type must be one of {tuple(TYPES)}")
    if service_type == "specialUse" and not subtype.strip():
        raise ValueError("specialUse requires an app-specific subtype explanation")
    path = Path(project) / "android/app/src/main/AndroidManifest.xml"
    ET.register_namespace("android", ANDROID)
    ET.register_namespace("tools", "http://schemas.android.com/tools")
    tree = ET.parse(path, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    manifest = tree.getroot()
    application = manifest.find("application")
    if application is None:
        raise ValueError("Android manifest has no application")
    service = next((s for s in application.findall("service") if s.get(NAME) == SERVICE), None)
    if service is None:
        service = ET.SubElement(application, "service", {NAME: SERVICE})
    service.set(f"{{{ANDROID}}}foregroundServiceType", service_type)
    service.set(f"{{{ANDROID}}}exported", "false")
    for prop in list(service.findall("property")):
        if prop.get(NAME) == "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE":
            service.remove(prop)
    if service_type == "specialUse":
        ET.SubElement(service, "property", {
            NAME: "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE",
            f"{{{ANDROID}}}value": subtype.strip(),
        })
    suffix = TYPES[service_type]
    if suffix:
        permission = f"android.permission.FOREGROUND_SERVICE_{suffix}"
        if not any(p.get(NAME) == permission for p in manifest.findall("uses-permission")):
            ET.SubElement(manifest, "uses-permission", {NAME: permission})
    tree.write(path, encoding="utf-8", xml_declaration=True)
