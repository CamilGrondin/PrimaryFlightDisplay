# Guide d'Utilisation - Nouvelles Améliorations

## 🚀 Démarrage rapide

### 1. Voir la démo des améliorations
```bash
# Depuis le répertoire du projet
python demo_improvements.py
```
Affiche des démonstrations pratiques de :
- Configuration centralisée
- Ajustement de fréquences COM
- Normalisation d'angles de cap
- Structures de télémétrie
- Customisation de configuration

### 2. Lancer les tests
```bash
# Tous les tests (34)
python -m unittest test_pfd -v

# Un test spécifique
python -m unittest test_pfd.TestCOMFrequencyAdjustment -v

# Avec résumé compact
python -m unittest test_pfd 2>&1 | grep -E "^test_|Ran|OK"
```

### 3. Accéder à la documentation
```bash
# Voir le guide complet des améliorations
cat IMPROVEMENTS.md

# Voir les docstrings dans VS Code
# → Ouvrir config.py, main.py, display.py, modes.py
# → Passer la souris sur les fonctions pour voir la documentation
# → Utiliser Ctrl+K Ctrl+I pour voir la signature complète
```

---

## 📖 Documentation des trois améliorations

### (1) Configuration Centralisée - `config.py`

**Qu'est-ce que c'est ?**
Un fichier unique qui contient tous les paramètres auparavant disséminés : résolutions d'écran, fréquences radio, pins GPIO, paramètres de joystick, etc.

**Pourquoi c'est utile ?**
- ✅ Modification facile des paramètres sans fouiller le code
- ✅ Support de scenarios différents (joystick, X-Plane, MSP)
- ✅ Facile à tester avec différentes configurations
- ✅ Prêt pour fichier de config JSON/YAML externe

**Comment l'utiliser ?**

```python
from config import Config

# Lire les valeurs
print(f"Résolution: {Config.screen.width}x{Config.screen.height}")
print(f"COM1: {Config.frequencies.com1:.3f} MHz")  
print(f"Joystick: {Config.joystick.name_hint}")

# Modifier un paramètre
Config.screen.max_fps = 120

# Charger depuis dictionnaire (ex: JSON)
custom_config = {
    "screen": {"width": 1920, "height": 1080, "max_fps": 120},
    "xplane": {"ip": "192.168.1.100", "port": 49000}
}
Config.from_dict(custom_config)

# Exporter vers dictionnaire (pour sauvegarder)
saved = Config.to_dict()
import json
with open("config.json", "w") as f:
    json.dump(saved, f, indent=2)
```

**Classes disponibles :**
```python
Config.screen          # Dimensions, FPS, masquage
Config.frequencies     # COM, NAV, limites
Config.joystick        # Paramètres manette
Config.xplane          # Connexion X-Plane
Config.msp             # Connexion MSP/série
Config.rotary          # Encodeur rotatif GPIO
Config.commands        # Commandes autopilote
```

---

### (2) Documentation Complète - Docstrings

**Qu'est-ce que c'est ?**
Descriptions détaillées de ce que font les fonctions, leurs paramètres, retours, et exceptions possibles.

**Où les voir ?**
- Dans VS Code : passer la souris sur une fonction → tooltip
- Terminal : `python -c "from main import _adjust_com_frequency; help(_adjust_com_frequency)"`
- Docstrings sont utilisés par IDE pour l'**autocomplétion** et l'**aide en ligne**

**Exemple :**
```python
def _adjust_com_frequency(current: float, steps: int, step_mhz: float) -> float:
    """Adjust COM1 frequency within valid aviation band range.

    Args:
        current: Current COM frequency in MHz.
        steps: Number of steps to adjust (positive or negative).
        step_mhz: Size of each step in MHz.

    Returns:
        Adjusted frequency, clamped to [118.000, 136.975] MHz range.
    """
```

**Fonctions documentées :**
- ✅ main.py (7 fonctions)
- ✅ display.py (2 classes/méthodes)
- ✅ modes.py (5 classes + 15+ méthodes)

**Bénéfice IDE :**
```python
# Dans VS Code, quand vous tapez :
from main import _adjust_com_frequency
_adjust_com_frequency(  # ← L'IDE affiche la signature complète
                        #   avec descriptions de paramètres
```

---

### (3) Suite de Tests Complète - `test_pfd.py`

**Qu'est-ce que c'est ?**
34 tests unitaires qui vérifient que les fonctions critiques fonctionnent correctement et qu'aucun changement ne les casse.

**Où les voir ?**
```bash
python -m unittest test_pfd -v
```

**Couverture des tests :**

| Domaine | Tests | Couverture |
|---------|-------|-----------|
| Ajustement fréquence COM | 7 | Haut/bas, limites, arrondi |
| Normalisation de cap | 5 | 0°, 360°, négatif, grand positif |
| Télémétrie | 4 | Défauts, customs, sérialisation |
| Configuration | 7 | Valeurs, import/export, validation |
| Autres (écran, radios, modes) | 6 | Complétude |
| **TOTAL** | **34** | ✅ 100% passing |

**Exemple de test :**
```python
def test_clamp_to_max(self):
    """Test frequency clamped to maximum COM band limit."""
    result = _adjust_com_frequency(136.900, steps=10, step_mhz=0.025)
    self.assertAlmostEqual(result, 136.975, places=3)
```

**Lancer les tests :**
```bash
# Tous
python -m unittest test_pfd -v

# Juste les fréquences COM
python -m unittest test_pfd.TestCOMFrequencyAdjustment -v

# Juste un test
python -m unittest test_pfd.TestCOMFrequencyAdjustment.test_adjust_frequency_up -v

# Avec coverage (si installé)
pip install coverage
coverage run -m unittest test_pfd
coverage report
```

---

## 🔗 Fichiers liés

| Fichier | Création | Description |
|---------|----------|-------------|
| `config.py` | ✨ Nouveau | Gestion centralisée de configuration |
| `test_pfd.py` | ✨ Nouveau | 34 tests unitaires |
| `demo_improvements.py` | ✨ Nouveau | Démonstration des améliorations |
| `IMPROVEMENTS.md` | ✨ Nouveau | Guide détaillé des améliorations |
| `main.py` | 📝 Mis à jour | Docstrings ajoutées |
| `display.py` | 📝 Mis à jour | Docstrings + type hints |
| `modes.py` | 📝 Mis à jour | Docstrings complètes |

---

## 💡 Cas d'usage

### Adapter pour une nouvelle manette de jeu
```python
from config import Config

# Avant : il fallait éditer modes.py
# Maintenant :
Config.joystick.name_hint = "Thrustmaster"
Config.joystick.max_turn_rate_deg_s = 15.0
Config.joystick.bank_deadzone_deg = 2.0
```

### Connecter à X-Plane distant
```python
Config.xplane.ip = "192.168.1.100"
Config.xplane.port = 49000
```

### Configurer résolution pour Raspberry Pi
```python
Config.screen.width = 800
Config.screen.height = 600
Config.screen.max_fps = 30
```

### Charger configuration depuis JSON
```python
import json
from config import Config

with open("custom_config.json", "r") as f:
    config_dict = json.load(f)
    
Config.from_dict(config_dict)
```

---

## ⚠️ Notes importantes

1. **Configuration est un singleton** : Les modifications à `Config` affectent toute l'app
2. **Tests isolent les changements de config** dans des blocs try/finally
3. **Type hints** améliorent IDE support mais ne sont pas forcés au runtime
4. **Docstrings** au format Google pour compatibilité avec sphinx/mkdocs

---

## 🎯 Prochaines étapes recommandées

1. **Charger config d'un fichier JSON au démarrage** :
   ```python
   import json
   with open("settings.json") as f:
       Config.from_dict(json.load(f))
   ```

2. **Remplacer print() par logging** :
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info(f"COM1 tuned to {freq:.3f}")
   ```

3. **Ajouter type checking avec mypy** :
   ```bash
   pip install mypy
   mypy --strict main.py modes.py display.py
   ```

4. **Tests dans CI/CD** (GitHub Actions) :
   ```yaml
   - name: Run tests
     run: python -m unittest discover
   ```

---

## 📞 Questions fréquentes

**Q: Comment customiser les fréquences radio ?**  
R: `Config.frequencies.com1 = 124.500` ou charger depuis JSON

**Q: Les tests ralentissent l'app ?**  
R: Non, ils s'exécutent avec `python -m unittest`, pas pendant l'exécution normale

**Q: Can I use the config from external files?**  
A: Yes! `Config.from_dict(json.load(f))` lets you load from JSON/YAML

**Q: Où mettre les docstrings pour nouvelles fonctions ?**  
R: Format Google (voir exemples dans config.py, main.py)

---

## 📚 Lectures recommandées

- [Google Style Python Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html)
- [unittest framework](https://docs.python.org/3/library/unittest.html)

---

**Dernière mise à jour:** 8 avril 2026  
**Améliorations appliquées:** Configuration, Documentation, Tests  
**Statut:** ✅ Complet et validé
