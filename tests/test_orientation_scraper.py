from scraper import classify_announcement, detect_announcement_type, find_best_apply_link, should_accept_publication_date


def test_should_accept_publication_date_only_for_2026():
    assert should_accept_publication_date("15 janvier 2026") is True
    assert should_accept_publication_date("12/03/2025") is False
    assert should_accept_publication_date("") is False


def test_classify_announcement_detects_bac_plus_two_from_eligibility():
    text = "Concours d'accès aux établissements de formation après DEUG, DEUST, DEUP, DUT ou diplôme équivalent"
    assert classify_announcement("Concours ENSEM", text, "", "") == "bac+2"


def test_classify_announcement_detects_ingenieur_cycle_admission():
    text = "Candidature pour l'accès en première année du cycle ingénieur dans les écoles d'ingénieurs"
    assert classify_announcement("Cycle ingénieur", text, "", "") == "ingenieur"


def test_detect_announcement_type_handles_inscription_and_bourse():
    assert detect_announcement_type("Inscription en ligne pour le concours", "") == "inscription"
    assert detect_announcement_type("Bourse d'études en France", "") == "bourse"


def test_find_best_apply_link_prefers_external_registration_platform():
    html = """
    <div>
      <a href="https://orientation-chabab.com/inscription">Orientation Chabab</a>
      <a href="https://pre-inscription.uh1.ac.ma/">S'inscrire</a>
      <a href="https://www.facebook.com/share">Facebook</a>
    </div>
    """
    result = find_best_apply_link(html, "https://orientation-chabab.com/article")
    assert result == "https://pre-inscription.uh1.ac.ma/"
