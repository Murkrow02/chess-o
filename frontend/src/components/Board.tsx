import { useEffect, useRef } from "react";
import { Chessground } from "chessground";
import type { Api } from "chessground/api";
import type { DrawShape } from "chessground/draw";
import type { Key } from "chessground/types";
import { Chess } from "chessops/chess";
import { chessgroundDests } from "chessops/compat";
import { makeFen, parseFen } from "chessops/fen";
import { makeSan } from "chessops/san";
import { parseSquare, parseUci } from "chessops/util";
import type { Side } from "../lib/types";

import "chessground/assets/chessground.base.css";

export interface BoardMove { uci: string; san: string; fen: string; capture: boolean; check: boolean; castle: boolean }

interface Props {
  fen: string;
  orientation: Side;
  lastMove?: [Key, Key];
  shapes?: DrawShape[];
  /** When set, the side to move can play and the move is reported here. */
  onMove?: (m: BoardMove) => void;
  /** Bump to snap the board back to `fen` (after a rejected try). */
  nonce?: number;
}

export function playUci(fen: string, uci: string): BoardMove | null {
  const pos = Chess.fromSetup(parseFen(fen).unwrap()).unwrap();
  const move = parseUci(uci);
  if (!move || !pos.isLegal(move)) return null;
  const san = makeSan(pos, move);
  pos.play(move);
  return { uci, san, fen: makeFen(pos.toSetup()), capture: san.includes("x"), check: /[+#]/.test(san), castle: san.startsWith("O-O") };
}

export function Board({ fen, orientation, lastMove, shapes, onMove, nonce }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const cg = useRef<Api | null>(null);
  const onMoveRef = useRef(onMove);
  onMoveRef.current = onMove;

  useEffect(() => {
    cg.current = Chessground(el.current!, {
      coordinatesOnSquares: false,
      animation: { enabled: true, duration: 180 },
      highlight: { lastMove: true, check: true },
      drawable: { enabled: true, visible: true, defaultSnapToValidMove: true, eraseOnClick: true },
      premovable: { enabled: false },
    });
    return () => cg.current?.destroy();
  }, []);

  useEffect(() => {
    const api = cg.current;
    if (!api) return;
    const setup = parseFen(fen).unwrap();
    const pos = Chess.fromSetup(setup).unwrap();
    const turn = setup.turn as Side;
    api.set({
      fen,
      orientation,
      turnColor: turn,
      lastMove,
      check: pos.isCheck() ? turn : undefined,
      movable: onMove
        ? {
            free: false,
            color: turn,
            dests: chessgroundDests(pos),
            showDests: true,
            events: {
              after: (orig: Key, dest: Key) => {
                let uci = `${orig}${dest}`;
                const piece = pos.board.get(parseSquare(orig)!);
                if (piece?.role === "pawn" && (dest[1] === "8" || dest[1] === "1")) uci += "q";
                const played = playUci(fen, uci);
                if (played) onMoveRef.current?.(played);
              },
            },
          }
        : { color: undefined, dests: new Map() },
    });
  }, [fen, orientation, lastMove?.[0], lastMove?.[1], Boolean(onMove), nonce]);

  useEffect(() => {
    cg.current?.setAutoShapes(shapes ?? []);
  }, [shapes]);

  return <div className="board-frame"><div ref={el} className="cg-wrap" /></div>;
}
