const axios = require("axios");
const qs = require("qs");

// 🔐 Your Azure credentials
const CLIENT_ID = "75f6446b-1b71-409f-85de-d003c13cd7d1";
const CLIENT_SECRET = "YOUR_CLIENT_SECRET_HERE";
const TENANT_ID = "0e222661-7d2f-4df7-b47d-85b52668be67";

// 📩 Sender & Receiver
const FROM_EMAIL = "kaji@kajenthiranPhotmail.onmicrosoft.com"; // must be in your tenant
const TO_EMAIL = "dj13mat2000@outlook.com";

// 🔑 Step 1: Get Access Token
async function getAccessToken() {
  const tokenUrl = `https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token`;

  const data = qs.stringify({
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    scope: "https://graph.microsoft.com/.default",
    grant_type: "client_credentials",
  });

  try {
    const response = await axios.post(tokenUrl, data, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });

    console.log("✅ Access Token Generated");
    return response.data.access_token;
  } catch (error) {
    console.error("❌ Token Error:", error.response?.data || error.message);
  }
}

// 📤 Step 2: Send Email
async function sendEmail() {
  const accessToken = await getAccessToken();

  const url = `https://graph.microsoft.com/v1.0/users/${FROM_EMAIL}/sendMail`;

  const emailData = {
    message: {
      subject: "Hello from Node.js 🚀",
      body: {
        contentType: "Text",
        content: "Mapla 😎 this email sent using Microsoft Graph API!",
      },
      toRecipients: [
        {
          emailAddress: {
            address: TO_EMAIL,
          },
        },
      ],
    },
  };

  try {
    const response = await axios.post(url, emailData, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
    });

    console.log("✅ Email sent successfully da!");
  } catch (error) {
    console.error("❌ Email Error:", error.response?.data || error.message);
  }
}

// 🚀 Run
sendEmail();