# GHOST

Arquivo pessoal local (Flask + SQLite). Etapas 1–2 concluídas: banco orientado a metadados e API.

## Executar (Windows)
1. Instale o Python 3.10+.
2. No terminal, na pasta do projeto: `python -m pip install -r requirements.txt`
3. `python app.py` (ou clique em `iniciar_ghost.bat`)
4. Acesse http://127.0.0.1:5000

O servidor escuta apenas em 127.0.0.1. Os dados ficam em `data/ghost.db`; para backup provisório, copie esse arquivo com o servidor parado. Executar localmente reduz a exposição, mas **não** criptografa os dados.

Na primeira inicialização, bancos de versões antigas são migrados automaticamente. O arquivo original é preservado como `data/ghost.legacy.db`.

## Testes
`python -m unittest discover -s tests`

## API (resumo)
`/api/collections`, `/api/collections/<id>/fields`, `/api/collections/<id>/records`, `/api/fields/<id>`, `/api/records/<id>`, `/api/search?q=`.
Operações destrutivas devolvem 409 até receberem `?confirm=true` (exclusão) ou `"confirm": true` (conversão de tipo).
