import { OpenAI } from "openai";
import fetch from "node-fetch";

const openai = new OpenAI({ apiKey: process.env.OPEN_API_KEY });

export default async (req, res) => {
  const { voiceIdA, voiceIdB, topic } = req.body;

  // 1. Wygeneruj dialog przez GPT
  const completion = await openai.chat.completions.create({
    model: "gpt-4o",
    messages: [
      {
        role: "system",
        content: "Generate a short, natural, 1-minute conversation (6–8 lines) between two people. Label lines with A: and B:. Keep it realistic.",
      },
      {
        role: "user",
        content: `Topic: ${topic}`,
      }
    ]
  });

  const lines = completion.choices[0].message.content
    .split("\n")
    .filter((l) => l.trim())
    .map((line, index) => {
      const [speaker, ...rest] = line.split(":");
      return {
        speaker: speaker.trim(),
        text: rest.join(":").trim(),
        voiceId: speaker.trim() === "A" ? voiceIdA : voiceIdB
      };
    });

  // 2. Wygeneruj audio dla każdej linii
  const results = await Promise.all(
    lines.map(async ({ speaker, text, voiceId }) => {
      const audioRes = await fetch("https://api.elevenlabs.io/v1/text-to-speech/" + voiceId, {
        method: "POST",
        headers: {
          "xi-api-key": process.env.ELEVEN_API_KEY,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          text,
          model_id: "eleven_multilingual_v2",
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.75,
            style: 0.0,
            use_speaker_boost: true
          }
        })
      });

      const buffer = await audioRes.arrayBuffer();
      const base64 = Buffer.from(buffer).toString("base64");
      const audio_url = `data:audio/mpeg;base64,${base64}`;

      return { speaker, text, audio_url };
    })
  );

  res.status(200).json({ dialogue: results });
};
