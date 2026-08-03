import pytest
from nhlgm.db import connect,migrate

@pytest.fixture
def db(tmp_path):
    d=connect(tmp_path/"test.db"); migrate(d); yield d; d.close()

