import { memo, useMemo } from "react";
import type { GameState, Tile } from "../types";
import "../styles/GameBoard.css";

type GameBoardProps = Pick<
  GameState,
  "width" | "height" | "tiles" | "hero" | "door"
>;

interface CellData {
  tile: Tile;
  x: number;
  y: number;
  hasHero: boolean;
  hasCarriedBlock: boolean;
  isDoor: boolean;
}

const tileLabels: Record<Tile, string> = {
  empty: "Empty tile",
  wall: "Wall",
  block: "Movable block",
  door: "Exit door"
};

const GameBoard = memo(({ width, height, tiles, hero, door }: GameBoardProps) => {
  const cells = useMemo<CellData[]>(() => {
    return tiles.map((tile, index) => {
      const x = index % width;
      const y = Math.floor(index / width);
      const hasHero = hero.x === x && hero.y === y;
      const hasCarriedBlock = hero.carrying && hero.x === x && hero.y - 1 === y;
      const isDoor = door.x === x && door.y === y;

      return { tile, x, y, hasHero, hasCarriedBlock, isDoor };
    });
  }, [tiles, width, hero, door]);

  return (
    <div
      className="game-board"
      role="grid"
      aria-label="Block Dude level"
      style={{
        gridTemplateColumns: `repeat(${width}, 1fr)`,
        gridTemplateRows: `repeat(${height}, 1fr)`
      }}
    >
      {cells.map((cell) => {
        const cellClasses = ["cell", `cell-${cell.tile}`];

        if (cell.isDoor) {
          cellClasses.push("cell-door");
        }

        return (
          <div
            key={`${cell.x}-${cell.y}`}
            role="gridcell"
            aria-label={`${tileLabels[cell.tile]}${
              cell.hasHero ? ". Player position" : ""
            }${cell.hasCarriedBlock ? ". Carrying block" : ""}`}
            className={cellClasses.join(" ")}
          >
            {cell.tile === "door" && <span className="door" aria-hidden="true" />}
            {cell.tile === "block" && <span className="block" aria-hidden="true" />}
            {cell.tile === "wall" && <span className="wall" aria-hidden="true" />}
            {cell.hasHero && (
              <span
                className={`hero hero-${hero.facing}`}
                aria-hidden="true"
                data-testid="hero"
              />
            )}
            {cell.hasCarriedBlock && <span className="block carried" aria-hidden="true" />}
          </div>
        );
      })}
    </div>
  );
});

GameBoard.displayName = "GameBoard";

export default GameBoard;
