import { GoogleGenAI } from '@google/genai';
import fs from 'fs';

const MINHA_CHAVE = 'AQ.Ab8RN6LIbxA2YrT7Reto7D0QedF_A71a3XrBNb4T59U66ayIFQ';

// Inicialização padrão do SDK do Gemini
const ai = new GoogleGenAI({ apiKey: MINHA_CHAVE });

function carregarImagemLocal(caminhoFicheiro) {
  const dadosDoFicheiro = fs.readFileSync(caminhoFicheiro);
  return {
    inlineData: {
      data: dadosDoFicheiro.toString('base64'),
      mimeType: 'image/jpg',
    },
  };
}

async function run() {
  try {
    const imagem = carregarImagemLocal('roupa.jpg');

    const prompt = `Apenas me envie o que vê nessa imagem de roupa nesse modelo aqui de JSON:
    {
      "nome": "",
      "cor": "",
      "estilo": "",
      "corte": "",
      "temperatura": "",
      "tipo": "",
      "material": "",
      "tamanho": "",
      "genero": "",
      "estacao": "",
      "imagem": "",
      "observacoes": ""
    }
    Se não for uma roupa retorne: "não é uma roupa bobo"`;

    const response = await ai.models.generateContent({
      model: 'gemini-3.8-flash',
      contents: [imagem, prompt],
    });

    console.log('Resposta do Gemini:\n', response.text);
  } catch (error) {
    console.error('Erro ao chamar a API:', error);
  }
}

run();
