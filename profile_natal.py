"""
Profile the natal chart calculator to identify performance bottlenecks.
"""

import cProfile
import pstats
import io
import time
from datetime import datetime
from natal import NatalChart, NodeType

def profile_chart_calculation():
    """Profile a single chart calculation with detailed timing."""

    print("=" * 75)
    print("NATAL CHART PERFORMANCE PROFILING")
    print("=" * 75)
    print()

    # Test chart data
    birth = datetime(1990, 6, 15, 14, 30, 0)

    # Overall timing
    start_total = time.perf_counter()

    # Profile with cProfile
    profiler = cProfile.Profile()
    profiler.enable()

    # Initialization
    start = time.perf_counter()
    chart = NatalChart(
        birth_date=birth,
        latitude=40.7128,
        longitude=-74.0060,
        timezone='America/New_York',
        house_system='Placidus',
        node_type=NodeType.TRUE,
        include_minor_aspects=True,
        include_angles_in_aspects=True
    )
    init_time = (time.perf_counter() - start) * 1000

    # Calculate planets
    start = time.perf_counter()
    chart.calculate_planets()
    planets_time = (time.perf_counter() - start) * 1000

    # Calculate houses
    start = time.perf_counter()
    chart.calculate_houses()
    houses_time = (time.perf_counter() - start) * 1000

    # Calculate Part of Fortune
    start = time.perf_counter()
    chart.calculate_part_of_fortune()
    pof_time = (time.perf_counter() - start) * 1000

    # Calculate aspects
    start = time.perf_counter()
    chart.calculate_aspects()
    aspects_time = (time.perf_counter() - start) * 1000

    # Add house positions to planets
    start = time.perf_counter()
    for planet_name in chart.planets:
        chart.planets[planet_name]['house'] = chart.get_planet_in_house(planet_name)
    house_positions_time = (time.perf_counter() - start) * 1000

    profiler.disable()
    total_time = (time.perf_counter() - start_total) * 1000

    # Print timing breakdown
    print("TIMING BREAKDOWN (milliseconds)")
    print("-" * 75)
    print(f"{'Operation':<40} {'Time (ms)':>12} {'Percent':>10}")
    print("-" * 75)
    print(f"{'Initialization (includes Julian day)':<40} {init_time:>12.3f} {init_time/total_time*100:>9.1f}%")
    print(f"{'Calculate planets ({} bodies)'.format(len(chart.planets)):<40} {planets_time:>12.3f} {planets_time/total_time*100:>9.1f}%")
    print(f"{'Calculate houses':<40} {houses_time:>12.3f} {houses_time/total_time*100:>9.1f}%")
    print(f"{'Calculate Part of Fortune':<40} {pof_time:>12.3f} {pof_time/total_time*100:>9.1f}%")
    print(f"{'Calculate aspects ({} found)'.format(len(chart.aspects)):<40} {aspects_time:>12.3f} {aspects_time/total_time*100:>9.1f}%")
    print(f"{'Determine planet house positions':<40} {house_positions_time:>12.3f} {house_positions_time/total_time*100:>9.1f}%")
    print("-" * 75)
    print(f"{'TOTAL':<40} {total_time:>12.3f} {'100.0%':>10}")
    print()

    # Print detailed profile stats
    print("=" * 75)
    print("DETAILED FUNCTION CALL STATISTICS (Top 20 by cumulative time)")
    print("=" * 75)

    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    ps.sort_stats('cumulative')
    ps.print_stats(20)
    print(s.getvalue())

    print("=" * 75)
    print("TOP 20 FUNCTIONS BY TIME SPENT (self time)")
    print("=" * 75)

    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    ps.sort_stats('time')
    ps.print_stats(20)
    print(s.getvalue())

    return chart

def benchmark_multiple_runs(num_runs=100):
    """Benchmark multiple chart calculations to get average performance."""

    print("=" * 75)
    print(f"BENCHMARK: {num_runs} CHART CALCULATIONS")
    print("=" * 75)
    print()

    birth = datetime(1990, 6, 15, 14, 30, 0)
    times = []

    for i in range(num_runs):
        start = time.perf_counter()

        chart = NatalChart(
            birth_date=birth,
            latitude=40.7128,
            longitude=-74.0060,
            timezone='America/New_York',
            house_system='Placidus',
            node_type=NodeType.TRUE,
            include_minor_aspects=True,
            include_angles_in_aspects=True
        )
        chart.generate_full_chart()

        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    print(f"Average time per chart: {avg_time:.3f} ms")
    print(f"Minimum time:          {min_time:.3f} ms")
    print(f"Maximum time:          {max_time:.3f} ms")
    print(f"Charts per second:     {1000/avg_time:.1f}")
    print()
    print(f"Estimated API throughput with uvicorn --workers 4:")
    print(f"  ~{(1000/avg_time) * 4:.0f} charts/second")
    print()

if __name__ == "__main__":
    # Detailed profiling of single calculation
    profile_chart_calculation()

    # Benchmark multiple runs
    print()
    benchmark_multiple_runs(100)
