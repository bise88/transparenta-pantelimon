#!/usr/bin/env python3
"""
monitor_uat.py — CLI wrapper pentru monitorizarea oricărui UAT românesc.

Utilizare:
    py monitor_uat.py <CIF> [--judet JUDET] [--nume "Numele UAT"] [--uat-search "Localitate"]

Exemple:
    py monitor_uat.py 4420759                              # Pantelimon (default)
    py monitor_uat.py 4364643 --judet Ilfov               # Voluntari
    py monitor_uat.py 4364660 --judet Ilfov --uat-search "Popesti-Leordeni"
    py monitor_uat.py 2837642 --judet B --uat-search "Sector 1"

Scriptul suprascrie CONFIG din monitor_pantelimon.py cu parametrii furnizați,
then rulează main() complet. Toate output-urile sunt scrise în directorul curent.

Notă: nu rula fără VPN / rate limiting activ — face scraping pe SEAP + ANAF.
"""
import argparse
import sys
import os


def parse_args():
    parser = argparse.ArgumentParser(
        description="Monitorizare cetateneasca UAT -- wrapper CLI multi-localitate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemple:
  py monitor_uat.py 4420759
  py monitor_uat.py 4364643 --judet Ilfov --uat-search Voluntari
  py monitor_uat.py 4364660 --judet Ilfov --uat-search Popesti-Leordeni --nume "Orasul Popesti-Leordeni"
        """,
    )
    parser.add_argument(
        "cif",
        help="CUI-ul primariei (ex: 4420759 pentru Pantelimon)",
    )
    parser.add_argument(
        "--judet",
        default=None,
        metavar="JUDET",
        help="Codul judetului (ex: IF, B, CL). Default: IF",
    )
    parser.add_argument(
        "--nume",
        default=None,
        metavar="NUME",
        help='Denumirea entitatii (ex: "Orasul Pantelimon"). Default: derivat din --uat-search',
    )
    parser.add_argument(
        "--uat-search",
        default=None,
        metavar="LOCALITATE",
        dest="uat_search",
        help='Termenul de cautare pentru UAT (ex: "Pantelimon"). Default: CIF',
    )
    parser.add_argument(
        "--email",
        default="",
        metavar="EMAIL",
        help="Email de contact (optional, pentru User-Agent)",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        metavar="DIR",
        dest="output_dir",
        help="Director pentru fisierele de output. Default: directorul curent",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Afiseaza CONFIG-ul calculat fara a rula monitorul",
    )
    return parser.parse_args()


def build_config_overrides(args):
    """Construiește dicționarul de suprascrieri CONFIG pe baza argumentelor CLI."""
    cif = str(args.cif).strip().lstrip("0")
    uat_search = args.uat_search or cif
    judet = (args.judet or "IF").upper()
    nume = args.nume or f"UAT {uat_search}"

    return {
        "cui":          cif,
        "nume_entitate": nume,
        "judet":        judet,
        "uat_search":   uat_search,
        "email_to":     args.email,
    }


def main():
    args = parse_args()

    # Schimbăm directorul de lucru dacă s-a specificat --output-dir
    if args.output_dir != ".":
        os.makedirs(args.output_dir, exist_ok=True)
        os.chdir(args.output_dir)

    overrides = build_config_overrides(args)

    print("=" * 60)
    print("  Monitor Transparenta UAT -- CLI multi-localitate")
    print("=" * 60)
    for k, v in overrides.items():
        print(f"  {k:20s}: {v}")
    print("=" * 60)

    if args.dry_run:
        print("\n[DRY RUN] CONFIG calculat. Monitorul NU a rulat.")
        print("Rulati fara --dry-run pentru a executa monitorizarea.")
        return 0

    # Import monitor_pantelimon și suprascriem CONFIG înainte de main()
    try:
        import monitor_pantelimon as mon
    except ImportError:
        print(
            "\n[EROARE] Nu am putut importa monitor_pantelimon.py.\n"
            "Asigurați-vă că rulați din același director cu monitor_pantelimon.py.",
            file=sys.stderr,
        )
        return 1

    # Suprascriem CONFIG cu parametrii CLI
    for key, value in overrides.items():
        mon.CONFIG[key] = value

    print(f"\n[START] Monitorizare {overrides['nume_entitate']} (CUI {overrides['cui']})…\n")

    try:
        mon.main()
    except KeyboardInterrupt:
        print("\n[INTRERUPT] Monitorizarea a fost oprita de utilizator.")
        return 130
    except Exception as exc:
        print(f"\n[EROARE] {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    print(f"\n[DONE] Fișierele au fost scrise în: {os.path.abspath('.')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
