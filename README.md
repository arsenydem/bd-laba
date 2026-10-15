# MiniDB

Файловая мини-СУБД: `meta.txt` (схема) и `<table>.dat` (строки через tab).

## Запуск

```
python main.py test_data init
python main.py test_data seed
python main.py test_data demo
python main.py test_data show
python main.py test_data select experiments id accuracy status where "status=completed AND accuracy>=0.9"
python main.py test_data select experiments id join datasets on dataset_id=id
python main.py test_data insert datasets 6 new cls 100
python main.py test_data update experiments status=stop where id=1
python main.py test_data delete experiments where status=failed
```

## Таблицы

datasets (id, name, task, size), models (id, name, version), experiments (id, dataset_id, model_id, accuracy, status). FK: dataset_id → datasets.id, model_id → models.id.

## Функции

CREATE (init/mk), INSERT, SELECT с колонками и WHERE (= != > < >= <=, AND/OR), UPDATE, DELETE, INNER JOIN, PK без дублей, проверка FK, сохранение на диск.
