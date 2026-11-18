import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))


@pytest.fixture(scope="session")
def base_sintetica(tmp_path_factory):
    from gerar_sintetico import gerar

    caminho = tmp_path_factory.mktemp("dados") / "sintetico.csv"
    gerar(n=6000, seed=1).to_csv(caminho, index=False)
    return caminho


@pytest.fixture(scope="session")
def modelo_treinado(base_sintetica, tmp_path_factory):
    """Treina um modelo pequeno numa pasta temporária (não mexe em modelos/ do projeto)."""
    from cademinhaconsulta import config
    from cademinhaconsulta.dados import preparar_base, separar_por_tempo
    from cademinhaconsulta.modelo import treinar

    pasta = tmp_path_factory.mktemp("modelos")
    mp = pytest.MonkeyPatch()
    mp.setattr(config, "DIR_MODELOS", pasta)
    mp.setattr(config, "ARQ_MODELO", pasta / "m.joblib")
    mp.setattr(config, "ARQ_METADADOS", pasta / "m.json")
    df = preparar_base(base_sintetica)
    modelo, relatorio = treinar(*separar_por_tempo(df), origem="teste")
    modelo.salvar()
    yield modelo, relatorio
    mp.undo()
