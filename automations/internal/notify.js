// Sends an alert by email (SendGrid) if you've set that up, falls back
// to SMS (Twilio), falls back to just logging. Never throws - a broken
// notifier shouldn't take down the actual compliance check.

require("dotenv").config();

async function sendAlert({ subject, message }) {
  const line = `[ALERT] ${subject}, ${message}`;

  const hasSendGrid = process.env.SENDGRID_API_KEY && process.env.ALERT_EMAIL_TO && process.env.ALERT_EMAIL_FROM;
  const hasTwilio = process.env.TWILIO_ACCOUNT_SID && process.env.TWILIO_AUTH_TOKEN && process.env.TWILIO_FROM_NUMBER && process.env.ALERT_SMS_TO;

  try {
    if (hasSendGrid) {
      const sgMail = require("@sendgrid/mail");
      sgMail.setApiKey(process.env.SENDGRID_API_KEY);
      await sgMail.send({
        to: process.env.ALERT_EMAIL_TO,
        from: process.env.ALERT_EMAIL_FROM,
        subject: `Medicare CRM: ${subject}`,
        text: message,
      });
      console.log(`${line} (sent via email)`);
      return;
    }
    if (hasTwilio) {
      const twilio = require("twilio");
      const client = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);
      await client.messages.create({
        to: process.env.ALERT_SMS_TO,
        from: process.env.TWILIO_FROM_NUMBER,
        body: `Medicare CRM: ${subject}, ${message}`.slice(0, 300),
      });
      console.log(`${line} (sent via SMS)`);
      return;
    }
    // nothing configured, that's fine, just log it
    console.log(`${line} (no SENDGRID_* or TWILIO_* env vars set, logged only)`);
  } catch (err) {
    // don't let a bad notification take the run down
    console.error(`notification failed for "${subject}": ${err.message}`);
  }
}

module.exports = { sendAlert };
