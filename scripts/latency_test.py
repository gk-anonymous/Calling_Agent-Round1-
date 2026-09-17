import argparse
import random
import statistics


def percentile(values, fraction):
    values = sorted(values)
    return values[min(len(values) - 1, int((len(values) - 1) * fraction))]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=5000)
    parser.add_argument("--mu", type=float, default=5.7)
    parser.add_argument("--sigma", type=float, default=0.55)
    args = parser.parse_args()
    samples = [random.lognormvariate(args.mu, args.sigma) for _ in range(args.samples)]
    print(f"samples={len(samples)} mean={statistics.mean(samples):.2f}ms p50={percentile(samples,.50):.2f}ms p90={percentile(samples,.90):.2f}ms p99={percentile(samples,.99):.2f}ms")


if __name__ == "__main__":
    main()
