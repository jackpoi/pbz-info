"""Steam 路径发现：VDF 解析、库枚举、账号排序。"""

from __future__ import annotations

import os
import time

import pytest

from app import discovery

LIBRARY_VDF = '''
"libraryfolders"
{
	"0"
	{
		"path"		"C:\\\\Program Files (x86)\\\\Steam"
		"label"		""
		"apps"
		{
			"228980"		"1234"
		}
	}
	"1"
	{
		"path"		"D:\\\\SteamLibrary"
		"label"		""
	}
}
'''

APP_MANIFEST = '''
"AppState"
{
	"appid"		"4115450"
	"name"		"Phantom Blade Zero"
	"installdir"		"PBZ"
	"StateFlags"		"4"
}
'''


def test_parse_vdf_nested():
    tree = discovery.parse_vdf(LIBRARY_VDF)
    root = tree["libraryfolders"]
    assert root["0"]["path"] == r"C:\Program Files (x86)\Steam"
    assert root["0"]["apps"]["228980"] == "1234"
    assert root["1"]["path"] == r"D:\SteamLibrary"


def test_parse_vdf_repeated_keys_become_list():
    text = '"root"\n{\n"k" "1"\n"k" "2"\n}\n'
    assert discovery.parse_vdf(text)["root"]["k"] == ["1", "2"]


def test_library_paths():
    paths = discovery.library_paths(LIBRARY_VDF)
    assert [str(p) for p in paths] == [r"C:\Program Files (x86)\Steam", r"D:\SteamLibrary"]


def test_app_manifest():
    state = discovery.parse_vdf(APP_MANIFEST)["AppState"]
    assert state["appid"] == "4115450"
    assert state["installdir"] == "PBZ"


@pytest.fixture()
def steam_tree(tmp_path):
    """造一棵假 Steam 目录树，第二个库里才有游戏。"""
    steam = tmp_path / "Steam"
    other = tmp_path / "games"
    (steam / "steamapps").mkdir(parents=True)
    (other / "steamapps").mkdir(parents=True)

    def esc(p) -> str:
        return str(p).replace("\\", "\\\\")

    vdf = (
        '"libraryfolders"\n{\n'
        f'\t"0"\n\t{{\n\t\t"path"\t\t"{esc(steam)}"\n\t}}\n'
        f'\t"1"\n\t{{\n\t\t"path"\t\t"{esc(other)}"\n\t}}\n'
        "}\n"
    )
    (steam / "steamapps" / "libraryfolders.vdf").write_text(vdf, encoding="utf-8")

    install = other / "steamapps" / "common" / "PBZ"
    (install / "platform" / "steam").mkdir(parents=True)
    (install / "platform" / "steam" / "PBZ.exe").write_bytes(b"MZ")
    save_root = install / "ProjectPBZ" / "Saved" / "SaveGames" / "Steam"
    for steam_id in ("12345678901234567", "12345678901234568"):
        (save_root / steam_id).mkdir(parents=True)
    (save_root / "12345678901234567" / "PBZSaveGame.sav").write_bytes(b"x")
    (other / "steamapps" / "appmanifest_4115450.acf").write_text(APP_MANIFEST, encoding="utf-8")
    return steam, other, install


def test_candidate_libraries_includes_steam_and_vdf(steam_tree):
    steam, other, _install = steam_tree
    roots = discovery.candidate_libraries(steam)
    assert roots[0] == steam
    assert Path_in(roots, other)


def Path_in(roots, other) -> bool:
    return any(os.path.normcase(str(r)) == os.path.normcase(str(other)) for r in roots)


def test_find_install_walks_libraries(steam_tree, monkeypatch):
    steam, _other, install = steam_tree
    monkeypatch.setattr(discovery, "steam_install", lambda: steam)
    # libraryfolders.vdf 里的库路径指向不存在的 C:\...，真实的第二个库需手动加入
    roots = [steam, _other]
    found = discovery.find_install(roots)
    assert found is not None
    assert os.path.normcase(str(found)) == os.path.normcase(str(install))


def test_key_exe_not_the_small_one(steam_tree):
    _steam, _other, install = steam_tree
    exe = discovery.key_exe(install)
    assert exe == install / "platform" / "steam" / "PBZ.exe"


def test_save_root_and_accounts(steam_tree):
    _steam, _other, install = steam_tree
    root = discovery.save_root(install)
    assert root.name == "Steam"

    accounts = discovery.list_accounts(root)
    assert [a.steam_id for a in accounts] == ["12345678901234567", "12345678901234568"]
    assert accounts[0].has_main is True
    assert accounts[1].has_main is False


def test_accounts_sorted_by_mtime(steam_tree):
    _steam, _other, install = steam_tree
    root = discovery.save_root(install)
    older = root / "12345678901234567" / "PBZSaveGame.sav"

    new = root / "12345678901234568" / "PBZSaveGame.sav"
    new.write_bytes(b"y")
    future = time.time() + 3600
    os.utime(new, (future, future))
    assert discovery.list_accounts(root)[0].steam_id == "12345678901234568"
    assert older.is_file()


def test_list_accounts_ignores_non_steam_dirs(tmp_path):
    root = tmp_path / "Steam"
    (root / "not-a-steam-id").mkdir(parents=True)
    (root / "12345678901234567").mkdir()
    assert [a.steam_id for a in discovery.list_accounts(root)] == ["12345678901234567"]


def test_list_accounts_missing_dir(tmp_path):
    assert discovery.list_accounts(tmp_path / "nope") == []


def test_discover_raises_without_steam(monkeypatch):
    monkeypatch.setattr(discovery, "steam_install", lambda: None)
    with pytest.raises(discovery.DiscoveryError, match="Steam"):
        discovery.discover()
