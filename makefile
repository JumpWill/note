# git commit and push
cp:
	git add .
	git commit -m"${m} $(shell date +%Y%m%d-%H%M%S)"
	git push
