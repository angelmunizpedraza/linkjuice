import glob
from pathlib import Path

from linkjuice import cli

FIX = Path(__file__).parent / "fixtures"


def _files():
    files = sorted(glob.glob(str(FIX / "*.html")))
    return [f for f in files if "home" in f] + [f for f in files if "home" not in f]


def test_run_on_local_files_writes_all_outputs(tmp_path):
    md, csvf, nodes = tmp_path / "r.md", tmp_path / "r.csv", tmp_path / "n.csv"
    code = cli.main([
        "run", *_files(), "--files", "--min-source-words", "100",
        "--md", str(md), "--csv", str(csvf), "--nodes-csv", str(nodes),
    ])
    assert code == 0
    text = md.read_text(encoding="utf-8")
    assert text.startswith("# linkjuice — internal link audit")
    assert "Orphan pages" in text and "Recommended new internal links" in text
    assert csvf.read_text(encoding="utf-8").startswith("source,target,similarity")
    assert "url,title,indexable" in nodes.read_text(encoding="utf-8")


def test_max_orphans_gate_fails(tmp_path, capsys):
    code = cli.main([
        "run", *_files(), "--files", "--min-source-words", "100",
        "--max-orphans", "0", "--md", str(tmp_path / "x.md"),
    ])
    assert code == 1
    assert "orphan pages" in capsys.readouterr().err


def test_max_orphans_gate_passes_when_generous(tmp_path):
    code = cli.main([
        "run", *_files(), "--files", "--min-source-words", "100",
        "--max-orphans", "10", "--md", str(tmp_path / "x.md"),
    ])
    assert code == 0


def test_missing_file_is_reported(capsys):
    assert cli.main(["run", "/nonexistent/page.html", "--files"]) == 2
    assert "file not found" in capsys.readouterr().err


def test_report_is_printed_when_no_output_path_is_given(capsys):
    assert cli.main(["run", *_files(), "--files", "--min-source-words", "100"]) == 0
    assert "internal link audit" in capsys.readouterr().out


def test_pipes_in_titles_do_not_break_the_markdown_table(tmp_path):
    md = tmp_path / "r.md"
    cli.main(["run", *_files(), "--files", "--min-source-words", "100", "--md", str(md)])
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ") and "---" not in line and "Page |" not in line:
            # 4-column rows must stay 4 columns: an unescaped pipe would add more
            assert line.count("|") - line.count("\\|") in (3, 4, 5), line
