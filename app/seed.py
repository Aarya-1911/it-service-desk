from app.database import engine, Base, SessionLocal
from app.models import User, Category, SLAConfig, RoleEnum, PriorityEnum

def init_and_seed():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed Categories if empty
        if not db.query(Category).first():
            categories = [
                Category(name="Hardware"),
                Category(name="Software"),
                Category(name="Network"),
                Category(name="Access / Permission"),
                Category(name="Email"),
                Category(name="Other")
            ]
            db.add_all(categories)
            print("✓ Categories seeded.")

        # 2. Seed SLA Configs if empty
        if not db.query(SLAConfig).first():
            sla_configs = [
                SLAConfig(priority=PriorityEnum.CRITICAL, resolution_hours=4),
                SLAConfig(priority=PriorityEnum.HIGH, resolution_hours=8),
                SLAConfig(priority=PriorityEnum.MEDIUM, resolution_hours=24),
                SLAConfig(priority=PriorityEnum.LOW, resolution_hours=48),
            ]
            db.add_all(sla_configs)
            print("✓ SLA Configurations seeded.")

        # 3. Seed Users if empty
        if not db.query(User).first():
            users = [
                User(name="Alice Employee", email="alice@company.com", role=RoleEnum.REQUESTER),
                User(name="Bob Requester", email="bob@company.com", role=RoleEnum.REQUESTER),
                User(name="Charlie IT Specialist", email="charlie@itdesk.com", role=RoleEnum.IT_AGENT),
                User(name="Diana IT Specialist", email="diana@itdesk.com", role=RoleEnum.IT_AGENT),
                User(name="Evan IT Manager", email="evan@itdesk.com", role=RoleEnum.MANAGER)
            ]
            db.add_all(users)
            print("✓ Sample Users seeded.")

        db.commit()
        print("Database initialized and seeded successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_and_seed()