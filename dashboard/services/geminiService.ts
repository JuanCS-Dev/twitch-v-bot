import { GoogleGenAI, GenerateContentResponse, Tool } from "@google/genai";
import { BotConfig } from "../types";

// Initialize the client
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });

interface BotResponse {
  text: string;
  image?: string;
  audio?: string;
}

/**
 * Helper to convert Raw PCM (16-bit, 24kHz, Mono) to WAV Blob URL
 * Gemini sends raw PCM without headers, browsers need WAV headers to play via <audio>
 */
const pcmToWav = (base64PCM: string): string => {
  const binaryString = atob(base64PCM);
  const len = binaryString.length;
  const buffer = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    buffer[i] = binaryString.charCodeAt(i);
  }

  // WAV Header parameters for Gemini defaults (usually 24kHz, 1 channel, 16-bit)
  const numChannels = 1;
  const sampleRate = 24000;
  const bitsPerSample = 16;
  const byteRate = sampleRate * numChannels * bitsPerSample / 8;
  const blockAlign = numChannels * bitsPerSample / 8;
  const dataSize = buffer.length;
  const headerSize = 44;
  const totalSize = headerSize + dataSize;

  const header = new ArrayBuffer(headerSize);
  const view = new DataView(header);

  // RIFF chunk descriptor
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true); // File size - 8
  writeString(view, 8, 'WAVE');

  // fmt sub-chunk
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true); // AudioFormat (1 for PCM)
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitsPerSample, true);

  // data sub-chunk
  writeString(view, 36, 'data');
  view.setUint32(40, dataSize, true);

  // Combine header and data
  const wavBytes = new Uint8Array(headerSize + dataSize);
  wavBytes.set(new Uint8Array(header), 0);
  wavBytes.set(buffer, headerSize);

  const blob = new Blob([wavBytes], { type: 'audio/wav' });
  return URL.createObjectURL(blob);
};

const writeString = (view: DataView, offset: number, string: string) => {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
};

export const testBotResponse = async (
  userMessage: string, 
  config: BotConfig
): Promise<BotResponse> => {
  try {
    // Default model
    let modelId = "gemini-3-flash-preview";
    
    // Command Parsing Logic
    let args = userMessage.trim().split(' ');
    let command = args[0].toLowerCase();
    let query = args.slice(1).join(' ');

    let finalPrompt = userMessage;
    let enableSearch = true; 
    let tempOverride = config.temperature;
    let isImageGeneration = false;
    let isAudioGeneration = false;

    // NLP / Heuristic Detection
    if (!userMessage.startsWith('!')) {
      const lowerMsg = userMessage.toLowerCase();
      
      // Image Keywords
      const imageKeywords = ['desenhe', 'crie uma imagem', 'gerar imagem', 'gera uma imagem', 'pintar um', 'fazer um desenho'];
      const hasImageIntent = imageKeywords.some(k => lowerMsg.startsWith(k) || lowerMsg.includes(` ${k} `));

      // Audio Keywords
      const audioKeywords = ['fale', 'diga', 'narre', 'gerar audio', 'criar audio', 'falar'];
      const hasAudioIntent = audioKeywords.some(k => lowerMsg.startsWith(k));

      if (hasImageIntent) {
        command = '!imaginar';
        query = userMessage;
      } else if (hasAudioIntent) {
        command = '!falar';
        // Remove the trigger word to make the prompt cleaner, or keep it. Let's keep it but guide the prompt.
        query = userMessage;
      }
    }

    // Command Logic Switch
    switch (command) {
      case '!pesquisa':
        finalPrompt = `Pesquise na web e responda detalhadamente sobre: "${query}". Use as informações mais recentes encontradas.`;
        enableSearch = true;
        break;

      case '!wiki':
        finalPrompt = `Gere um resumo informativo e estruturado (estilo Wikipédia, mas com linguagem descontraída) sobre: "${query}".`;
        enableSearch = true;
        break;

      case '!clima':
        finalPrompt = `Qual é a previsão do tempo atual, temperatura e condições para a cidade de: "${query}"?`;
        enableSearch = true;
        break;

      case '!historia':
        finalPrompt = `Crie uma história curta, criativa e envolvente (pode usar humor ou lore gamer) sobre o tema: "${query}".`;
        enableSearch = false; 
        tempOverride = 0.9;
        break;

      case '!traduzir':
        finalPrompt = `Traduza o seguinte texto para Português do Brasil (PT-BR), mantendo o tom original: "${query}"`;
        enableSearch = false;
        tempOverride = 0.3;
        break;

      case '!imaginar':
        modelId = "gemini-2.5-flash-image";
        finalPrompt = query || userMessage; 
        enableSearch = false;
        isImageGeneration = true;
        break;

      case '!falar':
        modelId = "gemini-2.5-flash-preview-tts";
        // Ensure we have a prompt for speech
        finalPrompt = query || "Olá! Eu sou o Gemini e estou pronto para conversar.";
        enableSearch = false;
        isAudioGeneration = true;
        break;

      case '!bot':
        finalPrompt = query;
        enableSearch = true;
        break;
        
      default:
        // Default chat behavior
        finalPrompt = userMessage;
        enableSearch = true;
        break;
    }

    // Configure Tools and Special Configs
    const tools: Tool[] = (enableSearch && !isImageGeneration && !isAudioGeneration) ? [{ googleSearch: {} }] : [];
    const generationConfig: any = {
       temperature: tempOverride,
    };

    if (!isImageGeneration && !isAudioGeneration) {
        generationConfig.tools = tools;
        generationConfig.systemInstruction = config.systemPrompt;
        generationConfig.maxOutputTokens = 600;
        generationConfig.thinkingConfig = {
            thinkingBudget: config.thinkingLevel === 'MINIMAL' ? 0 : 100
        };
    } else if (isImageGeneration) {
       generationConfig.imageConfig = { aspectRatio: "1:1" };
    } else if (isAudioGeneration) {
       generationConfig.responseModalities = ['AUDIO'];
       generationConfig.speechConfig = {
          voiceConfig: {
            prebuiltVoiceConfig: { voiceName: 'Kore' }, // Voices: Puck, Charon, Kore, Fenrir, Zephyr
          },
       };
    }

    // Construct the request
    const response: GenerateContentResponse = await ai.models.generateContent({
      model: modelId,
      contents: finalPrompt,
      config: generationConfig,
    });

    let text = "";
    let image: string | undefined = undefined;
    let audio: string | undefined = undefined;

    // Parse Response Parts (Text, Image, or Audio)
    if (response.candidates?.[0]?.content?.parts) {
        for (const part of response.candidates[0].content.parts) {
            if (part.text) {
                text += part.text;
            } else if (part.inlineData) {
                if (isImageGeneration) {
                    image = `data:${part.inlineData.mimeType};base64,${part.inlineData.data}`;
                    text = text || "Imagem gerada com sucesso:";
                } else if (isAudioGeneration) {
                    // Convert Raw PCM to WAV for playback
                    audio = pcmToWav(part.inlineData.data);
                    text = text || "Áudio gerado com sucesso:";
                }
            }
        }
    }

    if (!text && !image && !audio) text = "Sem resposta gerada.";

    // Handle Grounding Metadata (Sources) - Only for text
    if (!isImageGeneration && !isAudioGeneration && response.candidates?.[0]?.groundingMetadata?.groundingChunks) {
      const chunks = response.candidates[0].groundingMetadata.groundingChunks;
      const sources = new Set<string>();

      chunks.forEach((chunk: any) => {
        if (chunk.web?.uri) {
          sources.add(chunk.web.uri);
        }
      });

      if (sources.size > 0) {
        text += "\n\n🔍 Fontes:\n";
        sources.forEach(url => {
          text += `• ${url}\n`;
        });
      }
    }
    
    return { text, image, audio };
  } catch (error: any) {
    console.error("Gemini API Error:", error);
    return { text: `Erro no Sistema: ${error.message || "Falha na conexão neural."}` };
  }
};