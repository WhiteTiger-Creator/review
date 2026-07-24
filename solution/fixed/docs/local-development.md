# Local development

```bash
bundle install
bundle exec rails server -b 127.0.0.1 -p 3000
script/attest-local fixtures/archives/clean-compose.tar
bundle exec rspec
bundle exec rake corpus:status
```
