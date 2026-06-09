## Inicio
gh auth login
gh auth status

## Escolher
GitHub.com
HTTPS
Login with a web browser

## Para subir apenas 1 arquivo
git status
git add app/routes.py app/templates/base.html app/templates/datasync/index.html
git commit -m "Adiciona módulo DataSync com download de projetos"
git push

## Para subir tudo novamente
git status
git add .
git commit -m "Atualiza arquivos do projeto"
git push

## Fluxo para fazer sempre
git pull  
# faz alterações
git add .
git commit -m "Adiciona contador de downloads"
git push