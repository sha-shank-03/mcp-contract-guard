import argparse
import math
import sys

from .common import GuardError, MAX_FRAME, PROTOCOL_VERSION, SCHEMA_SHA256, paths_alias, write_document
from .contracts import offline_diff, snapshot_from
from .runner import Runner, cases_from


def duration(value):
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= 60:
        raise argparse.ArgumentTypeError("use a finite duration above 0 and at most 60 seconds")
    return number


def positive(value):
    number = int(value)
    if not 0 < number <= MAX_FRAME:
        raise argparse.ArgumentTypeError("use a positive bounded integer up to 1048576")
    return number


def tool_limit(value):
    number = positive(value)
    if number > 1000:
        raise argparse.ArgumentTypeError("the supported snapshot format permits at most 1000 tools")
    return number


def parser():
    cli = argparse.ArgumentParser(description="Bounded modern MCP stdio contract checks and offline diff; no model calls.")
    subs = cli.add_subparsers(dest="operation", required=True)
    for name in ("snapshot", "check", "diff"):
        sub = subs.add_parser(name)
        if name == "snapshot":
            sub.add_argument("--out", required=True)
        elif name == "check":
            sub.add_argument("--cases", required=True)
            sub.add_argument("--baseline", help="Consume a reviewed pinned snapshot without modifying it.")
        else:
            sub.add_argument("baseline")
            sub.add_argument("candidate")
            sub.set_defaults(execution_mode="offline_snapshot_diff")
        sub.add_argument("--report", help="Write the versioned JSON report, including failures.")
        sub.add_argument("--validation-timeout", type=duration, default=2.0)
        sub.add_argument("--run-timeout", type=duration, default=30.0)
        if name != "diff":
            sub.add_argument("--request-timeout", type=duration, default=2.0)
            sub.add_argument("--max-pages", type=positive, default=10)
            sub.add_argument("--max-tools", type=tool_limit, default=1000)
            sub.add_argument("--max-catalog-bytes", type=positive, default=MAX_FRAME)
            sub.add_argument("--execution-mode", choices=("local_stdio", "local_mock_stdio"), default="local_stdio",
                             help="Caller-supplied report label; use local_mock_stdio for the mock.")
            sub.add_argument("command", nargs=argparse.REMAINDER, help="After --, executable and literal arguments.")
    return cli


def validate_output_paths(args):
    outputs = [path for path in (getattr(args, "out", None), args.report) if path]
    inputs = [getattr(args, "cases", None), getattr(args, "baseline", None), getattr(args, "candidate", None)]
    for index, output in enumerate(outputs):
        for other in [*outputs[index + 1:], *[path for path in inputs if path]]:
            if paths_alias(output, other):
                raise GuardError("CONFIGURATION", "An output/report and another destination or input refer to the same file.",
                                 "Choose distinct files; collided paths will not be written.", exit_code=2)


def error_report(args, error, previous=None):
    report = dict(previous) if previous else {
        "reportVersion": 1, "protocolVersion": PROTOCOL_VERSION, "schemaSha256": SCHEMA_SHA256,
        "executionMode": args.execution_mode, "findings": [], "observations": [],
        "coverage": {"requestsExecuted": 0, "casesExecuted": 0}}
    report.update(status="fail", exitCode=error.exit_code)
    report["findings"] = [*report["findings"], {"ruleId": error.code, "summary": error.summary, "remedy": error.remedy}]
    return report


def main(argv=None):
    args = parser().parse_args(argv)
    output_paths_valid, report = False, None
    try:
        validate_output_paths(args)
        output_paths_valid = True
        if args.operation == "diff":
            code, report = offline_diff(snapshot_from(args.baseline), snapshot_from(args.candidate),
                                        validation_timeout=args.validation_timeout, run_timeout=args.run_timeout)
        else:
            command = args.command[1:] if args.command and args.command[0] == "--" else args.command
            if not command:
                raise GuardError("CONFIGURATION", "A server argument list is required after --.", "Specify an executable and literal arguments.", exit_code=2)
            cases = cases_from(args.cases) if args.operation == "check" else None
            baseline = snapshot_from(args.baseline) if args.operation == "check" and args.baseline else None
            runner = Runner(command, mode=args.execution_mode, request_timeout=args.request_timeout,
                            validation_timeout=args.validation_timeout, run_timeout=args.run_timeout,
                            max_pages=args.max_pages, max_tools=args.max_tools, max_catalog_bytes=args.max_catalog_bytes)
            code, report, snapshot = runner.run(cases, baseline)
            if snapshot is not None and args.operation == "snapshot":
                output_paths_valid = False
                validate_output_paths(args)
                output_paths_valid = True
                write_document(args.out, snapshot)
    except GuardError as error:
        code, report = error.exit_code, error_report(args, error, report)
    except OSError:
        print("LOCAL_IO: Cannot save the snapshot. Check the output path.", file=sys.stderr)
        return 2
    if args.report and output_paths_valid:
        try:
            validate_output_paths(args)
            write_document(args.report, report)
        except GuardError as error:
            code, report = error.exit_code, error_report(args, error, report)
        except OSError:
            print("LOCAL_IO: Cannot save the JSON report. Check the output path.", file=sys.stderr)
            return 2
    print(f"{report['status'].upper()} protocol={PROTOCOL_VERSION} mode={args.execution_mode} exit={code}")
    for finding in report["findings"]:
        path = finding.get("pointer", "") or "/"
        print(f"{finding['ruleId']} case={finding.get('caseId') or '-'} {path}: {finding['summary']}")
        print(f"  Action: {finding['remedy']}")
    for observation in report["observations"]:
        print(f"OBSERVATION {observation['ruleId']}: {observation['summary']}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
