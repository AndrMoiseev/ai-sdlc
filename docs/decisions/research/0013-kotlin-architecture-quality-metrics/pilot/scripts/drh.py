#!/usr/bin/env python3
"""Производные структурные метрики по графам зависимостей из metrics/deps-*.csv.

Обобщённое: ввод — любой ориентированный граф зависимостей
(CSV `from,to[,weight]`), метрики — чистая теория графов.

1. Design Rule Hierarchy (DRH; Braha & Bar-Yam, Sturtevant):
  1. Сверху срезаем «дизайн-правила» — узлы, не зависящие ни от одного
     из оставшихся (нет исходящих рёбер внутри остатка).
  2. Если таких нет — снизу срезаем «листья» — узлы, на которые никто
     из оставшихся не опирается (нет входящих).
  3. Если нет ни тех ни других — остаток циклический: самый большой сильно
     связный компонент становится «ядром» (клубком), убирается, продолжаем.

Слои сверху вниз: дизайн-правила -> ... -> [ядра] -> ... -> листья.
Направление ребра: from зависит от to.

2. Propagation cost (MacCormack–Rusnak–Baldwin, 2006): доля узлов, зависящих
от данного прямо или транзитивно (включая его самого); системный уровень —
среднее по всем узлам. «Если изменить узел, какую долю системы потенциально
затронет изменение».
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

M = Path(__file__).resolve().parent   # metrics/scripts
DATA = M.parent / 'data'  # артефакты снимка
ROOT = M.parent.parent    # корень репозитория


def load(name: str) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = {}
    with open(DATA / name, newline='') as f:
        for r in csv.DictReader(f):
            a, b = r['from'], r['to']
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set())
    return adj


def tarjan_sccs(adj: dict[str, set[str]], nodes: set[str]) -> list[set[str]]:
    """Итеративный Тарьян: список SCC."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on: set[str] = set()
    stack: list[str] = []
    sccs: list[set[str]] = []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(adj[root] & nodes))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(adj[w] & nodes)))
                    advanced = True
                    break
                elif w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                u = work[-1][0]
                low[u] = min(low[u], low[v])
            if low[v] == index[v]:
                scc: set[str] = set()
                while True:
                    w = stack.pop()
                    on.discard(w)
                    scc.add(w)
                    if w == v:
                        break
                sccs.append(scc)
    return sccs


def drh(adj: dict[str, set[str]]) -> tuple[list[list[str]], list[set[str]], list[list[str]]]:
    """Возвращает (слои сверху, ядра, слои снизу)."""
    nodes = set(adj)
    top: list[list[str]] = []
    cores: list[set[str]] = []
    bottom: list[list[str]] = []
    while nodes:
        tops = [v for v in nodes if not (adj[v] & nodes)]
        if tops:
            top.append(sorted(tops))
            nodes -= set(tops)
            continue
        bottoms = [v for v in nodes if not any(v in adj[u] for u in nodes)]
        if bottoms:
            bottom.append(sorted(bottoms))
            nodes -= set(bottoms)
            continue
        sccs = tarjan_sccs(adj, nodes)
        core = max(sccs, key=len)
        cores.append(core)
        nodes -= core
    return top, cores, bottom


def report(name: str, min_core: int = 0, summary: bool = False) -> None:
    adj = load(name)
    top, cores, bottom = drh(adj)
    n = len(adj)
    fan_in = {v: sum(1 for u in adj if v in adj[u]) for v in adj}
    print(f'\n===== {name}: {n} узлов =====')
    if summary:
        print(f'  слоёв сверху: {len(top)}; ядер: {len(cores)}; слоёв снизу: {len(bottom)}')
        print('  размеры верхних слоёв: ' + ', '.join(str(len(l)) for l in top))
        rules = sorted(top[0], key=lambda v: -fan_in[v])[:15] if top else []
        print('  дизайн-правила слоя 1 (по fan-in):')
        for v in rules:
            print(f'    {fan_in[v]:>3}  {v}')
        for core in cores:
            inside = sum(len(adj[v] & core) for v in core)
            print(f'  ЯДРО ({len(core)} узлов, {inside} рёбер внутри): ' + ', '.join(sorted(core)[:10]))
        return
    for i, layer in enumerate(top, 1):
        print(f'  слой {i} (дизайн-правила, {len(layer)}): ' + ', '.join(layer[:12]) + (' …' if len(layer) > 12 else ''))
    for core in cores:
        inside = sum(len(adj[v] & core) for v in core)
        if len(core) >= min_core:
            show = sorted(core)
            print(f'  ЯДРО ({len(core)} узлов, {inside} рёбер внутри): ' + ', '.join(show[:15]) + (' …' if len(show) > 15 else ''))
        else:
            print(f'  малый клубок ({len(core)}): ' + ', '.join(sorted(core)))
    for i, layer in enumerate(reversed(bottom), 1):
        print(f'  нижний {i} (листья, {len(layer)}): ' + ', '.join(layer[:12]) + (' …' if len(layer) > 12 else ''))
    if not cores:
        print('  циклов нет — граф ацикличен')


def propagation_cost(name: str, top: int = 10) -> None:
    """Видимость узлов (транзитивный fan-in + сам узел) и системный уровень."""
    adj = load(name)
    n = len(adj)
    radj: dict[str, set[str]] = {v: set() for v in adj}
    for a, bs in adj.items():
        for b in bs:
            radj[b].add(a)
    vis: dict[str, int] = {}
    for v in adj:
        seen = {v}
        stack = [v]
        while stack:
            for w in radj[stack.pop()]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        vis[v] = len(seen)
    total = sum(vis.values())
    print(f'\n===== propagation cost: {name} =====')
    print(f'  системный: {total / (n * n):.1%} (средняя видимость узла)')
    for v, k in sorted(vis.items(), key=lambda x: -x[1])[:top]:
        print(f'  {k / n:>5.1%}  {v}')


def cycle_edges(name: str) -> None:
    """Рёбра, замыкающие циклы в SCC, — конкретные цели для инверсии.

    Обобщённо: ребро (a, b) циклическое, если из b достижимо a без самого
    ребра. Жадная оценка разрыва: убираем самое тяжёлое циклическое ребро,
    пока в компоненте остаются SCC > 1 — число удалений даёт нижнюю оценку
    количества инверсий, необходимых для рассыпания клубка.
    """
    edges: dict[tuple[str, str], int] = {}
    nodes: set[str] = set()
    with open(DATA / name, newline='') as f:
        for r in csv.DictReader(f):
            edges[(r['from'], r['to'])] = int(r.get('weight', 1))
            nodes.add(r['from'])
            nodes.add(r['to'])
    print(f'\n===== циклические рёбра: {name} =====')

    def sccs_of(edge_set: dict[tuple[str, str], int]) -> list[set[str]]:
        a: dict[str, set[str]] = defaultdict(set)
        for u, v in edge_set:
            a[u].add(v)
        return [s for s in tarjan_sccs(a, set(a)) if len(s) > 1]

    if not sccs_of(edges):
        print('  циклов нет')
        return

    def reaches(start: str, goal: str, scc: set[str], banned: tuple[str, str],
                adj: dict[str, set[str]]) -> bool:
        seen, stack = {start}, [start]
        while stack:
            u = stack.pop()
            if u == goal:
                return True
            for v in adj[u] & scc:
                if (u, v) != banned and v not in seen:
                    seen.add(v)
                    stack.append(v)
        return False

    def cyclic_in(edge_set: dict[tuple[str, str], int], scc: set[str]) -> dict[tuple[str, str], int]:
        a: dict[str, set[str]] = defaultdict(set)
        for u, v in edge_set:
            a[u].add(v)
        return {e: w for e, w in edge_set.items() if e[0] in scc and e[1] in scc
                and reaches(e[1], e[0], scc, e, a)}

    for scc in sorted(sccs_of(edges), key=len, reverse=True):
        inner = {e: w for e, w in edges.items() if e[0] in scc and e[1] in scc}
        cyclic = cyclic_in(inner, scc)
        work, removed = dict(inner), []
        while True:
            cur = sccs_of(work)
            if not cur:
                break
            s = max(cur, key=len)
            cyc = cyclic_in(work, s)
            cut = max(cyc, key=lambda e: (cyc[e], e))
            del work[cut]
            removed.append((cut, cyc[cut]))
        short = lambda p: '.'.join(p.split('.')[-2:])
        print(f'  SCC из {len(scc)} узлов: рёбер внутри {len(inner)}, циклических {len(cyclic)};')
        print(f'  жадный разрыв — {len(removed)} инверсий: ' +
              ', '.join(f'{short(a)}→{short(b)}({w})' for (a, b), w in removed))


if __name__ == '__main__':
    min_core = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    report('deps-ctx.csv')
    report('deps-pkg.csv', min_core=min_core)
    report('deps-class.csv', summary=True)
    propagation_cost('deps-class.csv')
    propagation_cost('deps-pkg.csv')
    cycle_edges('deps-pkg.csv')
    cycle_edges('deps-class.csv')
