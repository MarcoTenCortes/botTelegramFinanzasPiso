# 📚 Idioma / Language

- [🇪🇸 Español](#español)
- [🇬🇧 English](#english)

## 🇪🇸 Español


# 🤖 Bot de Telegram para Finanzas Compartidas en un Piso

Este bot fue creado con el objetivo de **facilitar la convivencia económica** en un piso compartido de estudiantes. Gestionar una cuenta bancaria común puede ser caótico: pagos olvidados, saldos desconocidos, recordatorios que nadie cumple... Este bot automatiza gran parte de esa gestión.

## 🎯 Objetivo

La idea principal es ayudar a un grupo de personas que comparten una cuenta común a:
- Consultar saldos y transacciones de la cuenta compartida
- Saber quién ha pagado y quién no
- Programar recordatorios con notificaciones
- Automatizar avisos mensuales
- Añadir un poco de humor y personalización al proceso 😉

---

## 🛠️ Funcionalidades principales

- `/saldo`: Consulta los saldos actuales de la cuenta.
- `/transacciones`: Muestra las últimas 6 transacciones.
- `/iban`: Muestra los datos bancarios (IBAN, BIC, titular...).
- `/putoAntonio`: Detecta transferencias exactas de 800€ (uso interno divertido).
- `/morosos`: Informa quién **NO ha pagado** en los últimos 20 días.
- `/recordatorio YYYY-MM-DD HH:MM mensaje`: Programa un recordatorio.
- `/ListaRecordatorios`: Lista los recordatorios activos.
- `/borrarRecordatorio <id>`: Elimina un recordatorio por ID.
- `/chatid`: Muestra el ID del chat actual (útil para configuraciones).
- Comandos de humor: `/Rata`, `/InsultarMarco`, `/Huevos`, etc.

---

## 🧪 Uso

Se ejecuta como una app de línea de comandos con tres parámetros obligatorios:

```bash
python botTelegram.py --telegram_token <TU_TOKEN> --go_cardless_token <GC_TOKEN> --account_id <ID>
```

- `telegram_token`: El token de tu bot de Telegram.
- `go_cardless_token`: Token para acceder a la API de Open Banking.
- `account_id`: ID de la cuenta en GoCardless.

---

## 🔒 Seguridad

Este bot utiliza llamadas a APIs externas para consultar la cuenta bancaria. **No compartas los tokens** en público. Usa variables de entorno o argumentos de línea de comandos, pero nunca los subas al repositorio.

---

## 📦 Archivos ignorados

Asegúrate de tener un `.gitignore` con:

```
__pycache__/
*.pyc
reminders.json
.env
```

---

## 🙌 Créditos

Creado por y para compañeros de piso que prefieren discutir sobre quién fregó los platos, y no sobre quién olvidó pagar el alquiler 💸.

## 🇬🇧 English
# 🤖 Telegram Bot for Shared Flat Finances

This bot was created to **simplify financial cohabitation** in a student shared flat. Managing a joint bank account can be chaotic: forgotten payments, unknown balances, ignored reminders... This bot automates much of that hassle.

---

## 🎯 Purpose

The main idea is to help a group of people sharing a joint account to:
- Check balances and transactions
- Know who has paid and who hasn’t
- Schedule reminders with notifications
- Automate monthly payment alerts
- Add some humor and personalization to the process 😉

---

## 🛠️ Main Features

- `/saldo`: Check current account balances.
- `/transacciones`: Show the last 6 transactions.
- `/iban`: Display bank details (IBAN, BIC, account holder…).
- `/putoAntonio`: Detect exact €800 transfers (an internal joke).
- `/morosos`: Show who **hasn’t paid** in the last 20 days.
- `/recordatorio YYYY-MM-DD HH:MM message`: Schedule a reminder.
- `/ListaRecordatorios`: List active reminders.
- `/borrarRecordatorio <id>`: Delete a reminder by ID.
- `/chatid`: Display the current chat ID (useful for setup).
- Fun commands: `/Rata`, `/InsultarMarco`, `/Huevos`, etc.

---

## 🧪 Usage

Run it as a command-line app with three required parameters:

```bash
python botTelegram.py --telegram_token <YOUR_TOKEN> --go_cardless_token <GC_TOKEN> --account_id <ID>
```

- `telegram_token`: Your Telegram bot token.
- `go_cardless_token`: Token for accessing the Open Banking API.
- `account_id`: Your GoCardless account ID.

---

## 🔒 Security

This bot uses external API calls to access banking information.  
**Do not share your tokens publicly.** Use environment variables or command-line arguments, but never upload them to the repository.

---

## 📦 Ignored Files

Make sure you have a `.gitignore` with the following:

```
__pycache__/
*.pyc
reminders.json
.env
```

---

## 🙌 Credits

Built by and for flatmates who’d rather argue about who didn’t do the dishes than who forgot to pay the rent 💸

