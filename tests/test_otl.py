from ifcchef.otl import load_otl


def test_load_otl(otl_path):
    otl = load_otl(otl_path)

    assert otl == {
        "betonwand": {"objecttype", "materiaal"},
        "metselwerkwand": {"objecttype", "kleur"},
        "ruimte": {"objecttype", "ruimtenaam"},
    }
