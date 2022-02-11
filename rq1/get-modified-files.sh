for x in $(cd ../codebases/fenixedu-academic && git log --pretty=format:"%h");
	do echo $(cd ../codebases/fenixedu-academic && git diff-tree --no-commit-id --name-only -r $x);
done
