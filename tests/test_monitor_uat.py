"""
tests/test_monitor_uat.py
Faza 4-F CLI multi-UAT — monitor_uat.py teste unitare

Testele nu rulează monitorul complet (nu fac scraping).
Verifică parsing argumente, build config și comportament dry-run.
"""
import os
import sys
import subprocess
import json

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONITOR_UAT = os.path.join(REPO_ROOT, 'monitor_uat.py')

sys.path.insert(0, REPO_ROOT)


class TestMonitorUatArgs:

    def test_fisier_exista(self):
        """monitor_uat.py este prezent în repo."""
        assert os.path.exists(MONITOR_UAT)

    def test_syntax_valida(self):
        """monitor_uat.py trece py_compile fără erori."""
        import py_compile
        py_compile.compile(MONITOR_UAT, doraise=True)

    def test_help_returneaza_zero_sau_unu(self):
        """--help nu crasha (returnează 0)."""
        result = subprocess.run(
            [sys.executable, MONITOR_UAT, '--help'],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert 'cif' in result.stdout.lower()

    def test_dry_run_pantelimon(self):
        """Dry-run pentru CIF 4420759 returnează 0 și afișează CONFIG."""
        result = subprocess.run(
            [sys.executable, MONITOR_UAT, '4420759', '--dry-run'],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert '4420759' in result.stdout

    def test_dry_run_voluntari(self):
        """Dry-run pentru Voluntari cu --uat-search."""
        result = subprocess.run(
            [sys.executable, MONITOR_UAT, '4364643',
             '--judet', 'Ilfov', '--uat-search', 'Voluntari', '--dry-run'],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert '4364643' in result.stdout
        assert 'Voluntari' in result.stdout

    def test_dry_run_cu_nume(self):
        """--nume suprascrie numele UAT."""
        result = subprocess.run(
            [sys.executable, MONITOR_UAT, '4364660',
             '--nume', 'Orasul Popesti-Leordeni', '--dry-run'],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert 'Popesti-Leordeni' in result.stdout

    def test_dry_run_judet_uppercase(self):
        """--judet este convertit la uppercase."""
        result = subprocess.run(
            [sys.executable, MONITOR_UAT, '4420759',
             '--judet', 'ilfov', '--dry-run'],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0
        assert 'ILFOV' in result.stdout

    def test_fara_cif_eroare(self):
        """Fără CIF → exit code non-zero."""
        result = subprocess.run(
            [sys.executable, MONITOR_UAT],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode != 0


class TestBuildConfigOverrides:

    def test_import_function(self):
        """build_config_overrides importabilă din monitor_uat."""
        from monitor_uat import build_config_overrides
        assert callable(build_config_overrides)

    def test_config_contine_cui(self):
        """CONFIG override conține cui."""
        from monitor_uat import build_config_overrides, parse_args
        import argparse
        # Simulăm args manual
        args = argparse.Namespace(
            cif='4420759',
            judet='IF',
            nume=None,
            uat_search='Pantelimon',
            email='',
            output_dir='.',
            dry_run=False,
        )
        config = build_config_overrides(args)
        assert config['cui'] == '4420759'
        assert config['uat_search'] == 'Pantelimon'
        assert config['judet'] == 'IF'

    def test_config_judet_uppercase(self):
        """Judetul e convertit la uppercase."""
        from monitor_uat import build_config_overrides
        import argparse
        args = argparse.Namespace(
            cif='4364643',
            judet='ilfov',
            nume=None,
            uat_search='Voluntari',
            email='',
            output_dir='.',
            dry_run=False,
        )
        config = build_config_overrides(args)
        assert config['judet'] == 'ILFOV'

    def test_config_nume_derivat_din_uat_search(self):
        """Dacă --nume lipsește, numele e derivat din --uat-search."""
        from monitor_uat import build_config_overrides
        import argparse
        args = argparse.Namespace(
            cif='4420759',
            judet='IF',
            nume=None,
            uat_search='Pantelimon',
            email='',
            output_dir='.',
            dry_run=False,
        )
        config = build_config_overrides(args)
        assert 'Pantelimon' in config['nume_entitate']

    def test_config_nume_explicit(self):
        """--nume explicit suprascrie derivarea."""
        from monitor_uat import build_config_overrides
        import argparse
        args = argparse.Namespace(
            cif='4420759',
            judet='IF',
            nume='Municipiul Test',
            uat_search='Test',
            email='',
            output_dir='.',
            dry_run=False,
        )
        config = build_config_overrides(args)
        assert config['nume_entitate'] == 'Municipiul Test'
