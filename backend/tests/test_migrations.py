import os,subprocess,sys
from pathlib import Path
from sqlalchemy import create_engine,inspect,text
BACKEND=Path(__file__).resolve().parents[1]

def migrate(path,revision):
    env=dict(os.environ,DATABASE_URL='sqlite:///'+path.as_posix())
    r=subprocess.run([sys.executable,'-m','alembic','upgrade',revision],cwd=BACKEND,env=env,capture_output=True,text=True)
    assert r.returncode==0,r.stdout+r.stderr

def test_upgrade_and_fresh_install_have_equivalent_schema_and_preserve_history(tmp_path):
    old=tmp_path/'old.db';fresh=tmp_path/'fresh.db';migrate(old,'0002')
    engine=create_engine('sqlite:///'+old.as_posix())
    with engine.begin() as c:
        c.execute(text("INSERT INTO businesses (id,name,demo,mode,settings,version) VALUES ('business','Existing store',1,'standalone','{}',1)"))
        c.execute(text("INSERT INTO products (id,business_id,sku,name,brand,variant,size,unit,barcode,pack,sell_price,metadata) VALUES ('product','business','P','Legacy product','','','','unit','',12,30,'{}')"))
        c.execute(text("INSERT INTO movements (id,business_id,product_id,qty,kind,reason,at) VALUES ('movement','business','product',42,'opening','Legacy opening','2026-11-10 10:00:00')"))
        c.execute(text("INSERT INTO baskets (id,business_id,budget,status,version,lines,snapshot,feedback,created) VALUES ('basket','business',2000,'approved',3,'[]','{}','Keep approval','2026-11-10 10:00:00')"))
    migrate(old,'head');migrate(fresh,'head')
    fresh_engine=create_engine('sqlite:///'+fresh.as_posix())
    a,b=inspect(engine),inspect(fresh_engine)
    assert set(a.get_table_names())==set(b.get_table_names())
    for table in a.get_table_names():assert {c['name'] for c in a.get_columns(table)}=={c['name'] for c in b.get_columns(table)}
    with engine.connect() as c:
        assert c.execute(text('SELECT qty FROM movements')).scalar()==42
        assert c.execute(text('SELECT status,version,feedback FROM baskets')).one()==('approved',3,'Keep approval')
        assert c.execute(text("SELECT code FROM branches WHERE id=(SELECT branch_id FROM movements)")).scalar()=='MAIN'
    engine.dispose();fresh_engine.dispose()
