-- SQL queries for the "Надежда" quest (hope.json)

-- chapter_1: выбор всех объектов со статусом military
SELECT id, name, description, coordinates
FROM map
WHERE status = 'military';

-- chapter_2: top‑5 записей с максимальной importance (JOIN map и is_sensitive)
SELECT m.id, m.name, m.description, m.coordinates, s.importance
FROM map m
JOIN is_sensitive s ON m.id = s.id
ORDER BY s.importance DESC
LIMIT 5;

-- chapter_3: сведения о Танковом заводе и ЖД‑мосте (JOIN critical_objects)
SELECT m.id, m.name, co.description
FROM map m
JOIN critical_objects co ON m.id = co.id
WHERE m.name IN ('Танковый завод', 'ЖД-мост');

-- chapter_4: выбор результата решения (branching)
-- вариант 1 – разобраться с заводом
UPDATE decision SET result = 1;
-- вариант 2 – уничтожить мост
UPDATE decision SET result = 2;

-- chapter_5_1: выбор способа атаки (branching)
-- 10 – бомбардировка
UPDATE decision_factory SET result = 10;
-- 20 – подрыв заводом
UPDATE decision_factory SET result = 20;

-- chapter_5_1_10_1: сколько охранников active в секторе D, смена 22:00
SELECT s.shift_id, COUNT(g.guard_id) AS guard_count
FROM guards g
JOIN shifts s ON g.shift_id = s.shift_id
WHERE s.sector = 'D'
  AND s.start_time = '22:00'
  AND s.status = 'active'
GROUP BY s.shift_id;

-- chapter_5_1_10_2: термитовые заряды <1.5 кг в секторе D, охрана high/critical
SELECT i.item_id, i.name, i.weight
FROM items i
JOIN storages st ON i.storage_id = st.storage_id
WHERE i.type = 'thermite'
  AND i.weight < 1.5
  AND st.sector = 'D'
  AND st.security_level IN ('high', 'critical');

-- chapter_5_1_10_3: кратчайший low‑risk маршрут без активных блок‑постов в начале
SELECT r.route_id, r.start_sector, r.distance_km
FROM routes r
JOIN checkpoints cp ON r.start_sector = cp.sector
WHERE r.risk = 'low'
  AND cp.status <> 'active'
ORDER BY r.distance_km ASC
LIMIT 1;

-- chapter_5_1_10_5: шаблоны униформы (Germany, officer, approved)
SELECT dt.template_id, dt.name, d.activation_date
FROM disguise_templates dt
JOIN disguises d ON dt.template_id = d.template_id
WHERE dt.origin_country = 'Germany'
  AND dt.uniform_type ILIKE '%officer%'
  AND d.status = 'approved';

-- chapter_5_1_20_1: распределение предметов по карманам (weight ≤2 кг → Sasha, >2 кг → Grisha)
UPDATE items SET assigned_to = 'Sasha' WHERE weight <= 2;
UPDATE items SET assigned_to = 'Grisha' WHERE weight > 2;
