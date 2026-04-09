# Resume GPIO (Raspberry Pi)

Ce projet utilise la numerotation BCM de RPi.GPIO.

## GPIO utilises en execution (mapping actif dans main.py)

| GPIO BCM | Fonction | Module / Mode |
|---|---|---|
| 4 | Encodeur COM1 - voie A (CLK) | Com1RotaryTuner, tous modes |
| 17 | Encodeur COM1 - voie B (DT) | Com1RotaryTuner, tous modes |
| 27 | Encodeur COM1 - bouton SW | Com1RotaryTuner, tous modes |
| 22 | Encodeur COM1 - entree AUX | Com1RotaryTuner, tous modes |
| 5 | Bouton batterie (battery_switch) | XPlaneGPIOSwitchPanel, mode 2 |
| 6 | Bouton beacon_lights | XPlaneGPIOSwitchPanel, mode 2 |
| 13 | Bouton landing_lights | XPlaneGPIOSwitchPanel, mode 2 |
| 19 | Bouton taxi_lights | XPlaneGPIOSwitchPanel, mode 2 |
| 26 | Bouton nav_lights | XPlaneGPIOSwitchPanel, mode 2 |
| 20 | Bouton strobe_lights | XPlaneGPIOSwitchPanel, mode 2 |
| 21 | Bouton pitot_heat | XPlaneGPIOSwitchPanel, mode 2 |

## Configuration par defaut (config.py)

Le dataclass GPIOConfig contient les valeurs par defaut suivantes pour l'encodeur COM1 :

| GPIO BCM | Role par defaut |
|---|---|
| 17 | pin_a (CLK) |
| 27 | pin_b (DT) |
| 22 | pin_sw |
| 4 | pin_aux |

## Notes techniques

- Toutes les broches ci-dessus sont configurees en entree GPIO (gpio.IN).
- Pour les boutons du panneau X-Plane (mode 2), la lecture est active_low=True : un bouton appuye lit 1 (avec pull-up interne), un bouton relache lit 0.
- Les etats des boutons mode 2 sont envoyes vers X-Plane via UDP DataRef.
