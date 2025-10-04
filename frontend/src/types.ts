export type Tile = "empty" | "wall" | "block" | "door";

export interface Position {
  x: number;
  y: number;
}

export type Direction = "left" | "right";

export interface HeroState extends Position {
  facing: Direction;
  carrying: boolean;
}

export interface LevelDefinition {
  layout: string[];
  name: string;
}

export interface ParsedLevel {
  width: number;
  height: number;
  tiles: Tile[];
  heroStart: Position;
  door: Position;
  name: string;
}

export interface GameState extends ParsedLevel {
  levelIndex: number;
  hero: HeroState;
  moves: number;
  completed: boolean;
  message: string;
}
