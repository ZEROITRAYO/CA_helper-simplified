"""`flask seed` fills the rule tables, and backend/demo_data.sql loads on top of them."""

from sqlalchemy import func, select

from app.models import Business, CatalogService, Engagement, User
from app.seed import SERVICE_CATALOG
from app.utils import REPO_ROOT, verify_password

DEMO_SQL = REPO_ROOT / "backend" / "demo_data.sql"


def run_seed(app):
    result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0, result.output
    return result


def load_demo_sql(database):
    """Run the demo SQL file like psql would (it has its own BEGIN and COMMIT)."""
    connection = database.engine.raw_connection()
    try:
        connection.cursor().execute(DEMO_SQL.read_text())
        connection.commit()
    finally:
        connection.close()


def count(database, model):
    return database.session.scalar(select(func.count(model.id)))


def test_seed_command_lists_what_it_seeded(app, database):
    result = run_seed(app)

    assert "Seeded: service catalog, rule thresholds, obligation templates" in result.output


def test_seed_is_idempotent_and_adds_no_users(app, database):
    run_seed(app)
    run_seed(app)

    assert count(database, User) == 0  # the demo accounts come from demo_data.sql
    assert count(database, CatalogService) == len(SERVICE_CATALOG)
    # Each filing service knows its form (a request uses it to find the CA's price).
    gstr_3b = database.session.scalar(
        select(CatalogService).where(CatalogService.code == "gstr_3b")
    )
    tax_audit = database.session.scalar(
        select(CatalogService).where(CatalogService.code == "tax_audit")
    )
    assert gstr_3b.form_code == "gstr_3b"
    assert tax_audit.form_code is None


def test_the_demo_sql_loads_and_can_run_again(app, database, make_user):
    run_seed(app)
    teammate = make_user(email="teammate@example.com")

    load_demo_sql(database)
    load_demo_sql(database)  # it removes the old demo data first

    database.session.expire_all()
    assert count(database, User) == 22  # 21 demo accounts + the teammate, kept
    assert count(database, Business) == 14
    assert count(database, Engagement) == 16
    owner = database.session.scalar(select(User).where(User.email == "business@demo.local"))
    assert verify_password(owner.password_hash, "DemoBusiness#2026")
    assert database.session.get(User, teammate.id) is not None
