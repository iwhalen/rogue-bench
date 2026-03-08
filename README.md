# Rogue-Bench

This is a work in progress repository that forked my original project [here](https://github.com/iwhalen/rogomatic-llm).

It focuses more on portability and making the proof of concept into a real agent benchmark.

My to do list is:
- [ ] Dockerize Rogue Collection for portability
- [x] Implement headless version of Rogue for performance reasons
- [ ] Determine how to and then implement run seeding / saving
- [ ] Determine how to implement run saving in headless mode and when running in dockerized mode
- [ ] Reimplement the Rogue environment as a `gymnasium` environment
- [ ] Determine how to output score as the "reward" signal (is it just total gold?)
- [ ] Make it easier to add custom agents / agent harnesses