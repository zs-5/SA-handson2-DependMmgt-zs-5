#!/usr/bin/env python3
"""
Dependency Miner - Mine commits for dependency version changes using PyDriller

Usage:
	python dependency-miner.py <owner> <repo>

Example:
	python dependency-miner.py pac4j dropwizard-pac4j

Requirements:
	pip install pydriller python-dotenv
"""

import re
import sys
import pydriller
from pydriller import Repository
import os
from lxml import etree
import csv


def _parse_pom_dependencies(pom_xml_text):
	"""Extract dependencies from pom.xml text and return a dict of groupId:artifactId -> version.

	This function uses lxml to parse the XML content of a pom.xml file and extract the dependencies. It handles XML namespaces if present. The result is a dictionary where the key is "groupId:artifactId" and the value is the version string. If the pom.xml text is empty or None, it returns an empty dictionary. You can use it to parse a complete pom.xml file content. Use or delete.
	"""
	if not pom_xml_text:
		return {}

	tree = etree.fromstring(pom_xml_text.encode())

	# Extract namespace if present (pom.xml files often have a default namespace)
	nsmap = tree.nsmap
	namespace = nsmap.get(None)  # default namespace

	dependencies = {}

	if namespace:
		ns = {"m": namespace}
		dep_path = ".//m:dependency"
		group_path = "m:groupId"
		artifact_path = "m:artifactId"
		version_path = "m:version"
	else:
		ns = None
		dep_path = ".//dependency"
		group_path = "groupId"
		artifact_path = "artifactId"
		version_path = "version"

	for dep in tree.findall(dep_path, namespaces=ns):
		group = dep.find(group_path, namespaces=ns)
		artifact = dep.find(artifact_path, namespaces=ns)
		version = dep.find(version_path, namespaces=ns)

		if group is None or artifact is None:
			continue  # skip malformed dependencies

		group_id = group.text.strip()
		artifact_id = artifact.text.strip()
		version_text = version.text.strip() if version is not None else None

		key = f"{group_id}:{artifact_id}"
		dependencies[key] = version_text

	return dependencies


# Z: Why use a regex one when a proper parser one is available?
# def _parse_dependency_blocks(pom_xml_text):
# 	"""
# 	Parse XML text for <dependency> blocks and return dict of groupId:artifactId -> version.

# 	This helper function is provided to help you parse Maven pom.xml files. You can use it or delete if you don't need it. It uses regular expressions to find all <dependency> blocks and extract the groupId, artifactId, and version. The result is a dictionary where the key is "groupId:artifactId" and the value is the version string.
# 	"""
# 	deps = {}
# 	if not pom_xml_text or not pom_xml_text.strip():
# 		return deps
# 	# Find all <dependency>...</dependency> blocks (non-greedy, allow newlines)
# 	for block in re.findall(r"<dependency>(.*?)</dependency>", pom_xml_text, re.DOTALL):
# 		g = re.search(r"<groupId>([^<]+)</groupId>", block)
# 		a = re.search(r"<artifactId>([^<]+)</artifactId>", block)
# 		v = re.search(r"<version>([^<]+)</version>", block)
# 		if g and a and v:
# 			key = f"{g.group(1).strip()}:{a.group(1).strip()}"
# 			deps[key] = v.group(1).strip()
# 	return deps


def mine_repository(owner: str, repo: str) -> None:
	"""
	Main function to mine repository for dependency changes.

	Args:
		owner: Repository owner (e.g., 'pac4j')
		repo: Repository name (e.g., 'dropwizard-pac4j')
	"""
	repo_url = f"https://github.com/{owner}/{repo}"

	print(f"Analyzing repository: {owner}/{repo}")
	print(f"URL: {repo_url}")
	print("This may take a few minutes...\n")

	# Get commits with dependency changes
	commits_with_changes: list[pydriller.Commit] = []
	changes = []
	for commit in Repository(repo_url).traverse_commits():
		for m in commit.modified_files:
			if m.filename == "pom.xml" and m.change_type.name == "MODIFY" and _parse_pom_dependencies(m.source_code) != _parse_pom_dependencies(m.source_code_before):
				commits_with_changes.append(commit)

				before_deps = _parse_pom_dependencies(m.source_code_before)
				after_deps = _parse_pom_dependencies(m.source_code)
				per_commit_changes = []

				for dep in after_deps:
					# Dep added
					if dep not in before_deps:
						per_commit_changes.append(f"{dep}: added with version {after_deps[dep]}")
					# Dep version changed
					elif after_deps[dep] != before_deps[dep]:
						per_commit_changes.append(f"{dep}: version change from {before_deps[dep]} to {after_deps[dep]}")

				# Dep removed
				for dep in before_deps:
					if dep not in after_deps:
						per_commit_changes.append(f"{dep}: removed (previous version was {after_deps[dep]})")

				changes.append("; ".join(per_commit_changes))
	

	# Write output to csv
	output_filename = "output.csv"
	with open(output_filename, 'w') as csv_file:
		csv_writer = csv.writer(csv_file)
		csv_writer.writerow(["hash", "date", "author", "changes"])
		for commit, changes in zip(commits_with_changes, changes):
			csv_writer.writerow([commit.hash, commit.author_date, commit.author.name, changes])


	# Display results
	print(f"Repository: {owner}/{repo}")
	print(f"Commits with dependency changes: {len(commits_with_changes)}")
	print(f"\nCommit list saved to: {output_filename}")


def main():
	"""Main entry point for the script."""
	if len(sys.argv) != 3:
		print("Usage: python dependency-miner.py <owner> <repo>")
		print("Example: python dependency-miner.py pac4j dropwizard-pac4j")
		sys.exit(1)

	owner = sys.argv[1]
	repo = sys.argv[2]

	mine_repository(owner, repo)


if __name__ == "__main__":
	main()
