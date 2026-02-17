export interface ChatMessage {
  id: string;
  user: string;
  text: string;
  image?: string;
  audio?: string;
  timestamp: Date;
  isBot: boolean;
  sentiment?: 'positive' | 'neutral' | 'negative';
}

export interface BotConfig {
  systemPrompt: string;
  temperature: number;
  blockedWords: string[];
  isEnabled: boolean;
  thinkingLevel: 'MINIMAL' | 'BALANCED' | 'DEEP';
}

export enum BotStatus {
  ONLINE = 'ONLINE',
  OFFLINE = 'OFFLINE',
  THINKING = 'THINKING',
  ERROR = 'ERROR'
}

export interface AnalyticsData {
  time: string;
  messages: number;
  commands: number;
}

export interface SentimentData {
  name: string;
  value: number;
  fill: string;
}