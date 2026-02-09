"""Easing Gallery — Interactive easing curve visualizer.

Exercises tick-tween, tick-fsm, tick-schedule, and tick-signal.

Controls:
  Space   Launch wave (comparison) / spawn orb at center (sandbox)
  Tab     Toggle comparison / sandbox mode
  1-4     Select easing function (sandbox mode)
  A       Toggle auto-wave timer
  +/-     Adjust tween duration
  C       Clear all orbs
  Click   Spawn orb at cursor (sandbox mode)
  Esc     Quit
"""
from __future__ import annotations

import sys

import pygame

from tick import Engine
from tick_fsm import FSM
from tick_schedule import Timer
from tick_signal import SignalBus, make_signal_system
from tick_tween import Tween, make_tween_system
from tick_fsm import make_fsm_system
from tick_schedule import make_timer_system

from game.callbacks import make_on_tween_complete, make_on_timer_fire
from game.components import AutoWaveTag, OrbState
from game.guards import guards
from game.spawner import launch_wave, spawn_sandbox_orb
from ui.constants import (
    BG_COLOR,
    EASING_NAMES,
    FPS,
    SCREEN_H,
    SCREEN_W,
    SIDEBAR_W,
    STATUS_H,
    TPS,
)
from ui.lanes import draw_lanes
from ui.sandbox import draw_sandbox
from ui.status import draw_sidebar, draw_status_bar


class GameState:
    """Holds all game objects and state."""

    def __init__(self) -> None:
        self.engine = Engine(tps=TPS, seed=42)
        self.engine.world.register_component(OrbState)
        self.engine.world.register_component(AutoWaveTag)

        self.bus = SignalBus()

        # Track stats
        self.mode = "comparison"
        self.selected_easing = "linear"
        self.duration = 60  # ticks
        self.wave_count = 0
        self.complete_count = 0
        self.auto_wave = False
        self.auto_wave_eid: int | None = None

        # Subscribe to completion signal
        self.bus.subscribe("orb_complete", self._on_orb_complete)

        # Wire systems (order matters)
        on_complete = make_on_tween_complete(self.bus)
        on_fire = make_on_timer_fire(
            lambda: self._launch_wave(), lambda: self.duration
        )

        self.engine.add_system(make_tween_system(on_complete=on_complete))
        self.engine.add_system(make_fsm_system(guards=guards))
        self.engine.add_system(make_timer_system(on_fire=on_fire))
        self.engine.add_system(self._orb_time_system)
        self.engine.add_system(self._cleanup_system)
        self.engine.add_system(make_signal_system(self.bus))

    def _on_orb_complete(self, signal: str, data: dict) -> None:
        self.complete_count += 1

    def _launch_wave(self) -> None:
        launch_wave(self.engine.world, self.duration)
        self.wave_count += 1

    def _orb_time_system(self, world, ctx) -> None:
        """Sync OrbState.t from Tween.elapsed for curve dot tracking."""
        for eid, (orb, tween) in world.query(OrbState, Tween):
            orb.t = min(tween.elapsed / tween.duration, 1.0)

    def _cleanup_system(self, world, ctx) -> None:
        """Despawn completed orbs after a brief flash."""
        for eid, (orb, fsm) in list(world.query(OrbState, FSM)):
            if fsm.state == "completed":
                orb.t += 0.1
                if orb.t > 1.5:
                    world.despawn(eid)

    def toggle_auto_wave(self) -> None:
        """Toggle auto-wave timer on/off."""
        self.auto_wave = not self.auto_wave
        if self.auto_wave:
            eid = self.engine.world.spawn()
            self.engine.world.attach(eid, AutoWaveTag())
            self.engine.world.attach(
                eid, Timer(name="auto_wave", remaining=self.duration)
            )
            self.auto_wave_eid = eid
        else:
            if self.auto_wave_eid is not None:
                self.engine.world.despawn(self.auto_wave_eid)
                self.auto_wave_eid = None

    def clear_orbs(self) -> None:
        """Despawn all orb entities."""
        for eid, _ in list(self.engine.world.query(OrbState)):
            self.engine.world.despawn(eid)


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Easing Gallery — tick-tween demo")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 13)

    state = GameState()

    tick_interval = 1.0 / TPS
    accumulator = 0.0
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        accumulator += dt

        # --- Events ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_TAB:
                    state.mode = (
                        "sandbox" if state.mode == "comparison" else "comparison"
                    )

                elif event.key == pygame.K_SPACE:
                    if state.mode == "comparison":
                        state._launch_wave()
                    else:
                        # Spawn at center of playable area
                        cx = (SCREEN_W - SIDEBAR_W) / 2
                        cy = (SCREEN_H - STATUS_H) / 2
                        spawn_sandbox_orb(
                            state.engine.world,
                            state.selected_easing,
                            cx,
                            cy,
                            state.duration,
                        )

                elif event.key == pygame.K_a:
                    state.toggle_auto_wave()

                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    state.duration = min(state.duration + 20, 120)

                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    state.duration = max(state.duration - 20, 20)

                elif event.key == pygame.K_c:
                    state.clear_orbs()

                elif event.key == pygame.K_1:
                    state.selected_easing = EASING_NAMES[0]
                elif event.key == pygame.K_2:
                    state.selected_easing = EASING_NAMES[1]
                elif event.key == pygame.K_3:
                    state.selected_easing = EASING_NAMES[2]
                elif event.key == pygame.K_4:
                    state.selected_easing = EASING_NAMES[3]

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state.mode == "sandbox":
                    mx, my = event.pos
                    # Only spawn within the playable area
                    if mx < SCREEN_W - SIDEBAR_W and my < SCREEN_H - STATUS_H:
                        spawn_sandbox_orb(
                            state.engine.world,
                            state.selected_easing,
                            mx,
                            my,
                            state.duration,
                        )

        # --- Tick ---
        while accumulator >= tick_interval:
            state.engine.step()
            accumulator -= tick_interval

        # --- Render ---
        screen.fill(BG_COLOR)

        if state.mode == "comparison":
            draw_lanes(screen, state.engine.world, font)
        else:
            draw_sandbox(screen, state.engine.world, font)

        draw_sidebar(
            screen,
            font,
            wave_count=state.wave_count,
            complete_count=state.complete_count,
            duration=state.duration,
            tps=TPS,
            auto_wave=state.auto_wave,
            mode=state.mode,
            selected_easing=state.selected_easing,
        )
        draw_status_bar(screen, font, state.mode)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
