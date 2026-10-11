from pathlib import Path
import tempfile
import unittest
import zipfile

try:
    from research.ml.data_prep.read_support import read_support, safe_member_path
except ModuleNotFoundError as exc:
    if exc.name != "pypdf":
        raise
    read_support = safe_member_path = None


@unittest.skipIf(read_support is None, "Run support-reader tests with the bundled PDF runtime (pypdf)")
class SupportArchiveTests(unittest.TestCase):
    def test_path_traversal_and_windows_absolute_paths_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ["../outside.pdf", "/absolute.pdf", "C:/outside.pdf", "..\\outside.pdf"]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    safe_member_path(root, name)

    def test_allowed_members_only_and_original_archive_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root / "source", root / "cache"
            source.mkdir()
            archive = source / "schema.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("Schema/CDM20.avdl", "schema notes")
                stream.writestr("unexpected.exe", "do not extract")
            original = archive.read_bytes()
            result = read_support(source, output)
            self.assertEqual((output / "Schema/CDM20.avdl").read_text(), "schema notes")
            self.assertFalse((output / "unexpected.exe").exists())
            self.assertEqual(original, archive.read_bytes())
            self.assertEqual(len(result["documents"]), 1)

    def test_output_under_raw_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                read_support(Path(folder), Path(folder) / "out")


if __name__ == "__main__":
    unittest.main()
