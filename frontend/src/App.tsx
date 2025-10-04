import { useEffect, useMemo, useState } from "react";
import GameBoard from "./components/GameBoard";
import type { Direction, GameState, HeroState, LevelDefinition, Tile } from "./types";
import "./styles/App.css";

const LEVELS: LevelDefinition[] = [
  {
    name: "Warehouse Warmup",
    layout: [
      "############",
      "#..........#",
      "#......D...#",
      "#......#...#",
      "#......#...#",
      "#.....B#...#",
      "#H.B...#...#",
      "############"
    ]
  },
  {
    name: "Stacked Solutions",
    layout: [
      "##############",
      "#...........D#",
      "#..##...###..#",
      "#..##...#....#",
      "#..B....#....#",
      "#..B....##B..#",
      "#H.....B.....#",
      "##############"
    ]
  },
  {
    name: "Switchback Summit",
    layout: [
      "###############",
      "#.............#",
      "#....##..D....#",
      "#....##..##...#",
      "#..B....B#....#",
      "#..##.....##..#",
      "#H....B.......#",
      "###############"
    ]
  }
];

type Action =
  | "move-left"
  | "move-right"
  | "climb"
  | "toggle-carry"
  | "reset"
  | "next-level";

const handledKeys: Record<string, Action> = {
  ArrowLeft: "move-left",
  ArrowRight: "move-right",
  ArrowUp: "climb",
  Space: "toggle-carry",
  KeyR: "reset",
  KeyN: "next-level"
};

interface ParsedLevelData {
  tiles: Tile[];
  width: number;
  height: number;
  heroStart: { x: number; y: number };
  door: { x: number; y: number };
  name: string;
}

const getIndex = (width: number, x: number, y: number) => y * width + x;

const parseLevel = (definition: LevelDefinition): ParsedLevelData => {
  const height = definition.layout.length;
  const width = definition.layout[0]?.length ?? 0;
  const tiles: Tile[] = new Array(width * height).fill("empty");
  let heroStart = { x: 1, y: height - 2 };
  let door = { x: width - 2, y: 1 };

  definition.layout.forEach((row, y) => {
    if (row.length !== width) {
      throw new Error(`Inconsistent row width in level "${definition.name}"`);
    }

    [...row].forEach((char, x) => {
      const index = getIndex(width, x, y);

      switch (char) {
        case "#":
          tiles[index] = "wall";
          break;
        case "B":
          tiles[index] = "block";
          break;
        case "D":
          tiles[index] = "door";
          door = { x, y };
          break;
        case "H":
          heroStart = { x, y };
          tiles[index] = "empty";
          break;
        default:
          tiles[index] = "empty";
      }
    });
  });

  return {
    tiles,
    width,
    height,
    heroStart,
    door,
    name: definition.name
  };
};

const createInitialState = (levelIndex: number): GameState => {
  const definition = LEVELS[levelIndex];
  const parsed = parseLevel(definition);
  return {
    ...parsed,
    levelIndex,
    hero: {
      x: parsed.heroStart.x,
      y: parsed.heroStart.y,
      facing: "right",
      carrying: false
    },
    moves: 0,
    completed: false,
    message: "Reach the glowing exit door. Space picks up or drops blocks."
  };
};

const getTileFromArray = (
  tiles: Tile[],
  width: number,
  height: number,
  x: number,
  y: number
): Tile => {
  if (x < 0 || x >= width || y < 0 || y >= height) {
    return "wall";
  }

  return tiles[getIndex(width, x, y)];
};

const getTile = (state: GameState, x: number, y: number) =>
  getTileFromArray(state.tiles, state.width, state.height, x, y);

const isSolid = (tile: Tile) => tile === "wall" || tile === "block";

const finalizeState = (
  state: GameState,
  hero: HeroState,
  tiles: Tile[],
  moves: number
): GameState => {
  const completed = hero.x === state.door.x && hero.y === state.door.y;
  const message = completed
    ? `Level complete in ${moves} moves! Press N or Next Level to continue.`
    : state.message;

  return {
    ...state,
    tiles,
    hero,
    moves,
    completed,
    message
  };
};

const applyGravity = (
  hero: HeroState,
  tiles: Tile[],
  width: number,
  height: number
): HeroState => {
  const nextHero: HeroState = { ...hero };

  while (nextHero.y + 1 < height) {
    const below = getTileFromArray(tiles, width, height, nextHero.x, nextHero.y + 1);
    if (below !== "empty") {
      break;
    }

    if (nextHero.carrying) {
      const blockHeadroom = getTileFromArray(
        tiles,
        width,
        height,
        nextHero.x,
        nextHero.y
      );
      if (blockHeadroom !== "empty") {
        break;
      }
    }

    nextHero.y += 1;
  }

  return nextHero;
};

const withFacing = (hero: HeroState, facing: Direction): HeroState => ({
  ...hero,
  facing
});

const attemptMove = (state: GameState, direction: Direction): GameState => {
  const dx = direction === "left" ? -1 : 1;
  const intendedHero: HeroState = withFacing(state.hero, direction);
  const targetX = state.hero.x + dx;
  const targetY = state.hero.y;

  if (targetX < 0 || targetX >= state.width) {
    if (state.hero.facing === direction) {
      return state;
    }
    return { ...state, hero: intendedHero };
  }

  const targetTile = getTile(state, targetX, targetY);

  if (isSolid(targetTile)) {
    if (state.hero.facing === direction) {
      return state;
    }
    return { ...state, hero: intendedHero };
  }

  const headTile = getTile(state, targetX, targetY - 1);
  if (isSolid(headTile) || headTile === "door") {
    if (state.hero.facing === direction) {
      return state;
    }
    return { ...state, hero: intendedHero };
  }

  if (state.hero.carrying) {
    const carryHeadTile = getTile(state, targetX, targetY - 1);
    if (carryHeadTile !== "empty") {
      if (state.hero.facing === direction) {
        return state;
      }
      return { ...state, hero: intendedHero };
    }
  }

  let heroAfterMove: HeroState = {
    ...intendedHero,
    x: targetX,
    y: targetY
  };

  heroAfterMove = applyGravity(heroAfterMove, state.tiles, state.width, state.height);

  const moved = heroAfterMove.x !== state.hero.x || heroAfterMove.y !== state.hero.y;
  const facingChanged = state.hero.facing !== direction;

  if (!moved && !facingChanged) {
    return state;
  }

  const nextHero: HeroState = {
    ...heroAfterMove,
    carrying: state.hero.carrying
  };

  const moves = moved ? state.moves + 1 : state.moves;

  return finalizeState(state, nextHero, state.tiles, moves);
};

const attemptClimb = (state: GameState): GameState => {
  const dx = state.hero.facing === "left" ? -1 : 1;
  const frontX = state.hero.x + dx;
  const frontY = state.hero.y;

  const frontTile = getTile(state, frontX, frontY);
  if (!isSolid(frontTile)) {
    return state;
  }

  const targetX = frontX;
  const targetY = state.hero.y - 1;

  if (targetY < 0) {
    return state;
  }

  const landingTile = getTile(state, targetX, targetY);
  if (landingTile !== "empty" && landingTile !== "door") {
    return state;
  }

  const headroomTile = getTile(state, targetX, targetY - 1);
  if (state.hero.carrying) {
    if (headroomTile !== "empty") {
      return state;
    }
  } else if (isSolid(headroomTile)) {
    return state;
  }

  let heroAfterClimb: HeroState = {
    ...state.hero,
    x: targetX,
    y: targetY
  };

  heroAfterClimb = applyGravity(heroAfterClimb, state.tiles, state.width, state.height);

  if (heroAfterClimb.x === state.hero.x && heroAfterClimb.y === state.hero.y) {
    return state;
  }

  return finalizeState(state, heroAfterClimb, state.tiles, state.moves + 1);
};

const attemptPickUp = (state: GameState): GameState => {
  if (state.hero.carrying) {
    return state;
  }

  const dx = state.hero.facing === "left" ? -1 : 1;
  const blockX = state.hero.x + dx;
  const blockY = state.hero.y;

  if (blockX < 0 || blockX >= state.width) {
    return state;
  }

  const tile = getTile(state, blockX, blockY);
  if (tile !== "block") {
    return state;
  }

  const headroom = getTile(state, state.hero.x, state.hero.y - 1);
  if (headroom !== "empty") {
    return state;
  }

  const tiles = state.tiles.slice();
  tiles[getIndex(state.width, blockX, blockY)] = "empty";

  const hero: HeroState = {
    ...state.hero,
    carrying: true
  };

  return finalizeState(state, hero, tiles, state.moves + 1);
};

const attemptDrop = (state: GameState): GameState => {
  if (!state.hero.carrying) {
    return state;
  }

  const dx = state.hero.facing === "left" ? -1 : 1;
  const dropX = state.hero.x + dx;

  if (dropX < 0 || dropX >= state.width) {
    return state;
  }

  let dropY = state.hero.y;
  let tileAtTarget = getTile(state, dropX, dropY);

  if (tileAtTarget !== "empty") {
    return state;
  }

  while (dropY + 1 < state.height) {
    const below = getTileFromArray(state.tiles, state.width, state.height, dropX, dropY + 1);
    if (below === "empty") {
      dropY += 1;
      continue;
    }
    break;
  }

  tileAtTarget = getTileFromArray(state.tiles, state.width, state.height, dropX, dropY);
  if (tileAtTarget !== "empty") {
    return state;
  }

  const tiles = state.tiles.slice();
  tiles[getIndex(state.width, dropX, dropY)] = "block";

  const hero: HeroState = {
    ...state.hero,
    carrying: false
  };

  return finalizeState(state, hero, tiles, state.moves + 1);
};

const processAction = (state: GameState, action: Action): GameState => {
  switch (action) {
    case "move-left":
      return attemptMove(state, "left");
    case "move-right":
      return attemptMove(state, "right");
    case "climb":
      return attemptClimb(state);
    case "toggle-carry":
      return state.hero.carrying ? attemptDrop(state) : attemptPickUp(state);
    case "reset":
      return createInitialState(state.levelIndex);
    case "next-level":
      if (!state.completed) {
        return state;
      }
      return createInitialState((state.levelIndex + 1) % LEVELS.length);
    default:
      return state;
  }
};

const App = () => {
  const [state, setState] = useState<GameState>(() => createInitialState(0));

  const levelOptions = useMemo(
    () => LEVELS.map((level, index) => ({ label: level.name, value: index })),
    []
  );

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const action = handledKeys[event.code];
      if (!action) {
        return;
      }

      event.preventDefault();
      setState((current) => processAction(current, action));
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleLevelChange = (value: number) => {
    setState(createInitialState(value));
  };

  const handleNextLevel = () => {
    setState((current) =>
      createInitialState((current.levelIndex + 1) % LEVELS.length)
    );
  };

  const handleReset = () => {
    setState((current) => createInitialState(current.levelIndex));
  };

  return (
    <div className="app-wrapper">
      <header>
        <h1>Block Dude Revival</h1>
      </header>

      <div className="hud" role="status" aria-live="polite">
        <span>Level: {state.name}</span>
        <span>Moves: {state.moves}</span>
        <span>{state.hero.carrying ? "Carrying block" : "Hands free"}</span>
      </div>

      <GameBoard
        width={state.width}
        height={state.height}
        tiles={state.tiles}
        hero={state.hero}
        door={state.door}
      />

      <div className="controls">
        <strong>Controls</strong>
        <span>← →: walk</span>
        <span>↑: climb when facing a ledge</span>
        <span>Space: pick up or drop a block</span>
        <span>R: restart current level</span>
        <span>N: advance after clearing a level</span>
      </div>

      <div className="level-select">
        <label htmlFor="level-select">Jump to level:</label>
        <select
          id="level-select"
          value={state.levelIndex}
          onChange={(event) => handleLevelChange(Number(event.target.value))}
        >
          {levelOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.value + 1}. {option.label}
            </option>
          ))}
        </select>
        <button type="button" onClick={handleReset}>
          Reset Level
        </button>
        <button
          type="button"
          className="primary"
          onClick={handleNextLevel}
          disabled={!state.completed}
        >
          Next Level
        </button>
      </div>

      {state.message && <div className="status-banner">{state.message}</div>}

      <p className="footer-note">
        Inspired by the TI-83 Block Dude classic. Built for modern browsers with
        React + TypeScript.
      </p>
    </div>
  );
};

export default App;
